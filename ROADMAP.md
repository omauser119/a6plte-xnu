# SM-A605FN: XNU → Apple OSS ramdisk → Bash по SSH через USB

Первая конечная цель проекта: временно загрузить через lk2nd XNU 12377 и
Darwin ramdisk, собранный из открытых исходников Apple, затем подключиться с
компьютера по SSH через USB и получить интерактивный `/bin/bash` с рабочим PTY.
Все этапы сохраняют логи и panic на framebuffer. UART запрещён.

Статус на 19 октября 2026: на телефоне подтверждены штатные логи XNU,
VM bootstrap, регистрация платформы SM-A605FN, Apple pthread, запуск потоков
DLIL и self-tests Skywalk. Исправление описания CTRR прошло аппаратную проверку.
Ядро дошло до поиска корневого диска `Apple_HFS`; на последнем фото panic нет.
Сообщение об отсутствии NVRAM не является причиной ожидания rootfs.

В Actions успешно собран M2: настоящий драйвер Apple HFS+ из `hfs-715.120.4`,
32 MiB образ HFS+, передача `/chosen/memory-map/RAMDisk` и выбор `rd=md0`.
Пакет загрузчика сохраняет ядро и rootfs в проверенном свободном окне 256 MiB,
резервирует страницы образа от VM allocator и проверяет CRC всего содержимого.
Первый процесс `/sbin/a6-init` собирается как самостоятельный ARM64 Mach-O:
он должен открыть `/dev/console`, вывести PID и Darwin release, прочитать файл
из HFS+ и повторять секундный sleep/wakeup через настоящие системные вызовы.
Все три задания CI и проверки содержимого HFS+ прошли; это ещё предстоит
проверить на телефоне. Для увеличенного пакета установлен lk2nd с отображением
всего initrd перед копированием: старое окно 90 MiB было недостаточно. Нужна
аппаратная перезагрузка в обновлённый lk2nd перед повторным запуском. Bash, LibSystem и SSH пока отсутствуют.
Версия ядра исправлена с ошибочной `1.0.0d1` на Darwin `25.5.0` для XNU
`12377.121.6`; длительная работа планировщика и timer IRQ требуют проверки.

| Этап | Работа | Критерий завершения | Статус |
| --- | --- | --- | --- |
| M0. Загрузка и экран | lk2nd, Mach-O bridge, BootArgs/Apple DT, MMU, RGB888 console, native printf/kprintf/panic | Собственное ядро XNU выводит штатные логи после VM bootstrap | Подтверждено на телефоне |
| M1. Устойчивое ядро | Запустить IOKit platform expert, проверить GICv2 и виртуальный таймер, переключение потоков, ожидания и пробуждения, доступную RAM и криптографические зависимости | Несколько kernel threads работают 10 минут; проверены реальные timer IRQ, sleep/wakeup и отсутствие panic | В работе |
| M2. Корневой ramdisk | Расширить упаковщик, зарезервировать и отобразить образ в RAM, передать `RAMDisk` в Apple DT, подключить HFS+ и devfs | XNU создаёт `/dev/md0`, монтирует HFS+ как `/` и читает проверочный файл | Сборка и проверки образа прошли; аппаратная проверка ожидается |
| M3. EL0 и Darwin runtime | Первый ARM64 Mach-O процесс, системные вызовы, userspace VM, dyld, библиотеки LibSystem | Процесс из ramdisk выполняет write; затем динамический C-процесс проходит malloc, файлы, fork/exec/wait, signals и pthread smoke tests | Подготовлен первый PID1 probe; runtime запланирован |
| M4. PID1 и Bash | Минимальный ramdisk init, `/dev`, `/tmp`, учётные записи, Bash и базовые команды из Apple OSS | PID1 запускает `/bin/bash -c` со скриптами; работают команды, pipes, redirects, дочерние процессы и их сбор через wait | Запланировано |
| M5. USB peripheral | Qualcomm clocks/reset/power/USB2 PHY, DWC3 device mode, EP0, descriptors, bulk endpoints, DMA и IRQ | Компьютер перечисляет устройство, передача bulk проверена в обе стороны, повторное подключение работает | Запланировано |
| M6. Сеть через USB | CDC-ECM, Ethernet frames, BSD ifnet, IPv4/ARP/TCP, статические адреса | На Linux-хосте появляется USB Ethernet; работают двусторонний ping и TCP передача с проверкой данных | Запланировано |
| M7. SSH → интерактивный Bash | Apple OpenSSH, реальная криптография, host keys, авторизация по ключу, passwd/group lookup, PTY и job control | `ssh root@<usb-ip>` открывает Bash; работают Ctrl-C, размер терминала, pipeline, фоновые задания и повторный вход | Запланировано |
| M8. Первый законченный выпуск | Сборка ядра и rootfs в Actions, manifest исходников, артефакты, инструкция загрузки и проверка на телефоне | 10 успешных холодных запусков, 30 минут SSH-сессии, несколько USB reconnect без panic | Первая конечная цель |

Основная последовательность: **M1 → M2 → M3 → M4 → M7 → M8**.
После M1 USB-ветка **M5 → M6** может развиваться одновременно с ramdisk/userspace;
обе ветки сходятся в M7. Подбор и сборку исходников userspace можно начинать на
компьютере до готовности EL0, но успешная сборка не означает запуск на телефоне.

**Основа ramdisk — Apple Open Source.** Выбираем совместимые ревизии и фиксируем
commit, патчи, параметры сборки и зависимости в manifest. Ссылки ниже — проверенные
кандидаты исходников; точные версии userspace ещё не выбраны.

| Часть | Исходники и назначение |
| --- | --- |
| Ядро и syscall ABI | [XNU rel/xnu-12377](https://github.com/apple-oss-distributions/xnu/tree/rel/xnu-12377), включая `libsyscall` |
| C runtime | [Libc](https://github.com/apple-oss-distributions/Libc), [Libsystem](https://github.com/apple-oss-distributions/Libsystem), [libplatform](https://github.com/apple-oss-distributions/libplatform), [libpthread](https://github.com/apple-oss-distributions/libpthread), [libmalloc](https://github.com/apple-oss-distributions/libmalloc) |
| Динамическая загрузка | [dyld](https://github.com/apple-oss-distributions/dyld), адаптация для Cortex-A53 и выбранного набора библиотек |
| Shell и терминал | [Apple Bash](https://github.com/apple-oss-distributions/bash) — опубликованная ветка Bash 3.2 с патчами Apple; [ncurses](https://github.com/apple-oss-distributions/ncurses) для терминальных зависимостей |
| Команды | [shell_cmds](https://github.com/apple-oss-distributions/shell_cmds), [file_cmds](https://github.com/apple-oss-distributions/file_cmds), [system_cmds](https://github.com/apple-oss-distributions/system_cmds), минимально нужные утилиты |
| SSH | [Apple OpenSSH](https://github.com/apple-oss-distributions/OpenSSH), сборка автономного sshd и его криптографических зависимостей |
| Корневая FS | [hfs](https://github.com/apple-oss-distributions/hfs): HFS+ driver и инструменты создания образа |
| Локальные учётные записи | Аудит [Libinfo](https://github.com/apple-oss-distributions/Libinfo) и поддержка passwd/group lookup из файлов ramdisk |

Собственные части проекта — адаптация платы, загрузчик ramdisk, USB peripheral /
CDC-ECM и минимальный PID1 supervisor для этого окружения. PID1 монтирует devfs,
готовит writable-каталоги, запускает настройку сети и sshd, обрабатывает завершение
дочерних процессов. Полный launchd не является зависимостью первой конечной цели.

**M1: что необходимо закрыть до userspace.** Текущий HMAC-DRBG — bootstrap-путь,
который использует настоящий генератор XNU и boot entropy. Он не регистрирует
несуществующий corecrypto. Нужно инвентаризировать обязательные crypto callbacks
ядра, обеспечить полноценный источник случайных чисел и нужные криптографические
операции, проверить примитивы известными тестовыми векторами. Готовность этой части
для sshd проверяется отдельно от прохождения раннего `read_random`.

Таймер проверяем по аппаратным IRQ и выполнению нескольких потоков. Рост счётчика
в busy loop не засчитывает планировщик. Работу RAM расширяем только через
проверенные свободные диапазоны с учётом DT reservations, firmware, framebuffer,
скачанного пакета и памяти загрузчика; для пакета с rootfs загрузчик запрашивает проверенное окно 256 MiB;
пакеты без rootfs сохраняют прежние 128 MiB.

**M2–M4: реальный rootfs и процессы.** В XNU уже есть путь
`/chosen/memory-map/RAMDisk` → `mdevadd` и выбор `rd=md0` в
[IOKitBSDInit.cpp](https://github.com/apple-oss-distributions/xnu/blob/ac9718fb1af618d5ce8678d0dc6e8a58f252216f/iokit/bsddev/IOKitBSDInit.cpp).
Передача и резервирование RAMDisk реализованы в bridge. Драйвер Apple HFS+
включён в сборку с регистрацией native VFS и встроенной IOKit personality.
Монтирование и чтение файла нужно подтвердить на телефоне; само появление
`md0` не доказывает работу файловой системы.

Начальный EL0 probe можно собрать с минимальными зависимостями, затем вводить
динамический runtime и реальные программы. Все исполняемые файлы собираются под
обычный ARM64/Cortex-A53; архитектурные пути с обязательными PAC/LSE для этой платы
исключаются или адаптируются. У [Libsystem есть большой список зависимостей](https://github.com/apple-oss-distributions/Libsystem/blob/main/requiredlibs),
поэтому состав библиотек и версии dyld/Libc выбираются совместно. Зависимости от
системных служб разбираются до включения компонента в образ. Заголовки SDK для
сборки не заменяют собранные из исходников runtime-библиотеки.

**M5–M7: USB и SSH.** В текущем DT платы описан Qualcomm DWC3 с USB2 PHY,
режимом peripheral и максимальной скоростью high-speed; это исходная точка для
проверки регистров и питания на железе. Для первого подключения выбираем
CDC-ECM и Linux-хост. USB перечисление, bulk transport и Ethernet/TCP проверяются
последовательно. UART, USB serial и работающий в lk2nd fastboot не заменяют
USB-драйвер самого XNU.

Предварительный адресный план: компьютер `192.168.77.1/30`, телефон
`192.168.77.2/30`; при конфликте с сетью хоста адреса меняются. DHCP и маршрутизация
в Интернет не требуются для первой SSH-сессии. На этапе OpenSSH нужны автономные
user/group lookup, `/dev/ptmx` и PTY, обработка сигналов, рабочие часы/таймеры,
поддерживаемые шифры и ключи. Private host keys и `authorized_keys` не включаются
в публичный универсальный образ: ключи создаются на устройстве либо подаются при
локальной сборке персонального ramdisk. На экране можно показать fingerprint.

**Как принимается M8.** После настройки USB-интерфейса на компьютере:

```sh
ssh root@192.168.77.2
uname -a
printf '%s\n' "$BASH_VERSION"
id
printf 'ramdisk ok\n' > /tmp/probe
cat /tmp/probe | wc -c
sleep 2
```

Это будущая проверка, а не уже работающая команда подключения. Дополнительно
проверяются Ctrl-C, изменение размера терминала, `sleep 30 &` / `jobs` / `fg`,
запуск внешних команд, закрытие сессии и повторный вход после переподключения USB.
Kernel logs остаются на дисплее на протяжении всей проверки.

Выпуск включает `xnu-boot.img` с ядром и rootfs, отдельные kernel/ramdisk для
диагностики, подходящий lk2nd, SHA-256, manifest исходников и инструкцию хоста.
Готовность M8 означает самостоятельное Darwin-окружение с интерактивным Bash по
SSH через USB. Дальнейшие задачи проекта — eMMC, сохранение данных, SMP, питание
и остальные драйверы платы.
