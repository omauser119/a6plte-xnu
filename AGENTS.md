# Указания пользователя для SM-A605FN

- UART запрещён. Логи ядра и panic выводить на framebuffer.
- Пока оставить `/sbin/a6-init`. Дальнейшие userspace, SSH и Bash отложены
  до команды пользователя. Код USB сохранять, запуск оставлять выключенным.
- Будущая команда пользователя **«чеснок»** означает: реализовать и проверить
  загрузку с корневого HFS+ тома на GPT-разделе `userdata` вместо ramdisk.
  Пользователь сам подготовит HFS+ и разместит на нём свой userspace.
  Эта команда разрешает работу по переключению загрузки; повторно спрашивать
  разрешение на уже запрошенное переключение не нужно.
- Упоминание слова при установке или объяснении этого условия не является
  командой переключения. До будущей команды сохранять текущую загрузку с ramdisk.
- При переключении проверить фактические GPT, границы и HFS+, использовать
  ограниченный разделом драйвер. Не форматировать `userdata`, не подменять
  подготовленный пользователем userspace и не записывать другие разделы.

## Текущая команда

Команда «чеснок» уже получена: подготовить корень HFS+ на `userdata` и запуск
`/sbin/launchd` с него. Пользователь отдельно выбрал `launchd`.
Команда **«паста»** получена 2026-10-20. Проверенный образ уже загружен через
`fastboot boot`; повторного разрешения на эту проверку не требуется.

Текущая задача: отдельный такой же образ на настоящих исходниках XNU
8796.141.3 / Darwin 22.6.0 в ветке `xnu-8796`. Сохранить 12377 в `main`.
Корень `userdata`, PID1 `/sbin/launchd`, USB выключен, UART запрещён.
Запись образа в `boot` пользователь пока только обсуждает; прошивка не запрошена.

Последнее указание пользователя: **временно отключить SMP**. Все boot-профили
теперь передают штатный `cpus=1`; native ml_parse_cpu_topology исключает AP
до a6_start_other_cpus, поэтому CPU1–CPU7 не получают PSCI CPU_ON. Код SMP
сохранён, но не включать обратно без запроса пользователя. PRNG сохранять.

Базовое ядро 8796: источник `9caba04`, все три задания Actions 39299095063 успешны.
Образ `/home/damstik/a6plte-xnu-8796/artifacts/xnu-8796-userdata-boot.img`,
SHA-256 `71ae2dbf0c4b150eb70b37e22de139e7a53ac24500f1bf6d62468e9767c73ec8`, 16992256 байт.
Проверен скачанный CI-образ; ядро для символизации —
`/home/damstik/a6plte-xnu-8796/build/verified-9caba04/kernel/kernel.a6plte`.
Первый запуск дошёл до exec launchd: пользователь сообщил SIGKILL,
namespace 9 / code 0xe (EXEC_EXIT_REASON_WRONG_PLATFORM). Профиль DEVELOPMENT
macOS отклонял iOS PID1 без атрибутов posix_spawn. В userdata-профиль добавлен
штатный `unentitled_ios_sim_launch=1`; проверки подписи не отключены.
Образ перепакован с тем же ядром, полный CRC/профиль проверен и повторно
загружен через fastboot (OKAY). Текущий образ по указанному пути имеет SHA-256
`01434528a7b6a8ee4f67f87b0c76ce8be4e5fc2d007ea46a2a9aad7407143a41`.
Результат второго запуска пока не сообщён. Основной заголовок userdata HFSX
проверен чтением: 4096-байтные блоки, 4194304 блока, том 16 ГиБ.

## Следующая проверка и дополнения

Второй запуск прошёл WRONG_PLATFORM, но пользователь сообщил отказ подписи
dyld shared cache: `unsupported code signature page shift: 14`.
Добавлена настоящая проверка 16-КиБ CodeDirectory на 4-КиБ ядре: перед
публикацией подписи проверяются полные блоки и выводятся 4-КиБ хеши; VM fault
проверяет реальные страницы по этим хешам, без I/O под VM lock и без чтения
16 КиБ из 4-КиБ буфера. Исходные CodeDirectory/cdhash не изменяются.
ASan/UBSan тесты с четырьмя алгоритмами, порчей данных, scatter, частичными
страницами и ошибками выделения/I/O прошли; native ubc_subr.c компилируется.

Пользователь дополнительно запросил адаптацию ios-sweet 0050–0057 и 0064:
permissive Sandbox, crash heap strings (SIGABRT/SIGTRAP, SpringBoard),
HFS rename swap, process sampler 16 кадров/40 снимков, AKS selectors 35/101,
ограничение частоты показа кадров, CONFIG_EXT_RESOLVER off, work interval.
Поведение 0050–0057 и 0064 адаптировано: compat.c, a6plte_diagnostics.c,
HFS regular-file exchange fallback, AKS DER 17/35 и consume 101, framebuffer
shadow/timer, CONFIG_EXT_RESOLVER off. Добавлены Galaxy A6+ identity и
явный IOPMPowerSource/AppleSmartBattery стаб 100%. Полные host-тесты,
включая DER/bounds, прошли; compat.c и diagnostics.c native header probes
прошли. C++ и kpi_vfs.c требуют Apple Clang (Linux не имеет allocator builtins).
Исходные патчи сохранены только как reference, commit
`11da58bd050672960c0a83b5bef2176047eea479`; HID 0058 удалён и не применяется.
Также нужны идентичность Samsung Galaxy A6+, реальные размеры дисплея,
явный стаб батареи 100%, реальные кнопки громкости/питания и тачскрин S6SY761.
**HID Sweet запрещён последним указанием пользователя: писать собственный HID.**
Тачскрин: I2C QUP 0x078b6000, адрес 0x48, IRQ TLMM GPIO59; volume-up GPIO85,
power/resin (volume-down) PM8953 PON. Данные из reference/a6plte-r4.dts.
Последний запрос: SMP всех восьми Cortex-A53. DT использует PSCI smc;
MPIDR 0,1,2,3,0x100,0x101,0x102,0x103. Нельзя ограничиться сменой cpus=1:
нужны per-CPU trampoline/MMU/IRQ/таймер и реальная проверка включения.

664d6e1: все три задания Actions 39399742651 успешны. Проверенный образ
с 16-КиБ проверкой подписи: build/verified-664d6e1/images/xnu-8796-userdata-boot.img,
SHA256 a70b9ed5881e18eeaa72aca1cc10f8a36a532aac427c521bc16166f2ef0d1e47.
Ядро build/verified-664d6e1/kernel/kernel.a6plte, SHA256
f59d9f5d5072ad27fcda55813956c5e9ca5305c028bc6a6a6b54d930992e7e98.
Образ 664d6e1 загружен через fastboot boot (OKAY), пользователь прислал фото:
`16 KiB signature verified; 4 KiB page hashes ready`. Следующий отказ dyld:
shared cache `(null)` not loaded, `/usr/lib/libSystem.B.dylib` отсутствует как
отдельный файл, PID1 namespace 6 / subcode 1. Пока не доказана причина отказа
shared cache: проверять mapping/slide, не подменять userspace.

bf20c51: все задания Actions 39405039587 успешны (совместимость/AKS/батарея/FB).
На телефоне пока проверено только ядро 664d6e1.

Добавлен SMP-путь: MAX_CPUS=8, два кластера MPIDR AFF1/AFF0, восемь DT CPU,
PSCI CPU_ON, собственный physical AP entry -> native per-CPU stacks/MMU,
GICv2 banked init и SGI1 IPI, native registration/start + ожидание online.
Framebuffer защищён reentrant межъядерной блокировкой только после MMU;
до MMU атомики не используются. Host ASan/UBSan тесты (включая восемь
параллельных писателей и точное сравнение framebuffer) прошли. Native asm/C
probes прошли. SMP пока не проверен на телефоне; честный итог — только после
отчёта online и реальной работы AP. Sweet HID не использовать.


952dec2: read-only split dyld cache preflight (native header/subcache UUID/path
checks), signed-coverage and mapping syscall results. All Actions 39408904675
passed. Hardware result pending. No shared-cache root cause asserted yet.

e36f008: SMP kernel all Actions 39407189812 passed. Verified downloaded image:
build/verified-e36f008/images/xnu-8796-userdata-boot.img, SHA256
ff6960f807519bd10f387ab278326a7ea2173760c3a9ef595f0449dbf1cf333f.
Not booted yet; readiness question pending (hardware-reset into lk2nd).

Original HID implemented in A6HID.cpp, A6Input.c/.h, A6HIDWire.c/.h, with no
Sweet HID source. Physical S6SY761 on BLSP1 QUP2, TLMM GPIO6/7/59/139;
volume-up GPIO85, read-only PM8953 PON RT_STS over SPMI observer for power
and volume-down. Clocks from msm8953-mainline/linux d9eabbae3edea6adb08e74c30059aa0933afaae7.
No firmware update, power/reset PMIC writes, UART, or USB startup. Public Apple
event-service queue ABI, ESUC open/close/copy, core IOSharedDataQueue, digitizer
collections/ten contacts and consumer volume/power keys. This is a subset of
IOHIDFamily, not proof of working backboardd/UI. Hardware not tested yet.
Host ASan/UBSan tests cover FIFO repeated START, coordinates/slots/release,
PON read-only commands, debounce, bounded timeout, HID wire sizes/capacity.


Hardware 952dec2 boot accepted (image SHA256
84f52d5f1bf7b7a2ba6b37d78a164ee4385878a87a10111f3a387653a92bd8c1),
but failed on the FIRST CPU before MMU: ESR 0x96000000, ELR physical
0x44c0e360, FAR 0xfffffff007085220. Matched linked disassembly precisely:
_a6_xnu_puts+0xa0 reads virtual string selected by _a6_xnu_stage's compiler
lookup table. Longer SMP-locked puts changed optimizer decisions. It is not
an AP fault. Fix 350d906 applies -fno-jump-tables to early.c/fb.c; compiled
stage now uses direct ADRP/ADD strings, with no absolute relocations. Add
regression check to host and native platform builds. Readiness question pending.

32541a4 and 521c50d (own HID and DT calibration) passed all native Actions.
HID hardware not yet booted. Sensor axes use the board DT's 4096-unit ranges
(max 4095); display stays 1080x2220. No Sweet HID sources were used.


350d906 native build passed all Actions 39411714320. Downloaded kernel
SHA256 c0d8d8af7ab208286a61bd98556ed50f9353c358219e8c6991270a607be4c271.
Locally packaged/checked userdata image SHA256
d41d34f6c07da2b47324ebecdbdc100cccf82c52b378050e4972fc4575847fa9,
boot accepted, early MMU issue passed. User now reports
`random_cpu_init: kernel prng has not been installed` during AP registration.
The standalone port had only the boot HMAC-DRBG fallback, no external corecrypto
kext. 97dbdb4 moves registration/start after EARLY_BOOT/spllo; that alone is
insufficient and must NOT be booted as the PRNG fix.
f260bf3 explicitly installs native HMAC-SHA256 DRBG root/per-CPU instances via
register_and_init_prng, using real bootseed, distinct root-derived CPU seeds,
per-generator locks with IRQs masked and native entropy refresh/reseed.
random_cpu_init guard stays intact. Native header probe passed, full CI pending.
Readiness question pending after the PRNG panic.
For fast artifact fetch use scripts/download-ci-kernel.py RUN_ID. It downloads
only the linked kernel in parallel ranges and verifies GitHub archive SHA256;
package locally and run check-userdata-boot.py. No need to download both boot
images as well (slow CDN was ~50 KiB/s per connection).


f260bf3: all Actions 39414369814 passed. Latest ready image:
build/verified-f260bf3/images/xnu-8796-userdata-boot.img (17094656 bytes), SHA256
9f5962a1517096493493b0f3db400fb5d0f09026a05bf00155da39f41d1cbbdd.
Kernel SHA256 b498e8ce26c7d10379672d00eac0227f55783084a60aedd700650144d1d2be6e.
Verified native early-stage disassembly has three ADRP strings and no pointer
lookup, SMP/PRNG markers and full kernel/payload CRC/profile. Fastboot accepted
this image after the user returned the device. User then requested SMP off.
No renewed pasta approval is needed. UART and USB network remain disabled.

Latest boot: same native f260bf3 kernel, bridge locally rebuilt with cpus=1
for every profile. Immutable image:
build/verified-f260bf3/cpu0/xnu-8796-userdata-cpu0-boot.img, SHA256
9066f36735b8b11c24c9859016d7dc8f288a65a624cf9ccf58a73326235a1c06.
Complete CRC/native version/CPU0 profile validated. Boot accepted in 0.487 s;
private receipt artifacts/boot-f260bf3-cpu0.private.log. User reports it reached
dyld, with S6SY761 probe failed and dyld cache '(null)' not loaded '(null)'.
Need exact input reg/value and A6PLTE dyld preflight/signed/map lines; async
question pending. This confirms first-CPU path to dyld, not working touch/SMP.

Next diagnostics: explicit W1C of QUP I2C error status before transfers, keep
the original FIFO/bus error across cleanup, report sensor register/boot/integrity
failures and command. Host ASan/UBSan regression includes stale NACK, ongoing
FIFO error plus failed cleanup, and sensor stuck in bootloader. dyld_diag now
retains preflight/split-cache, signature errno/coverage, mmap and map2 results;
prints a compact summary immediately before PID1 panic, including saved touch
probe status. No files or signature checks modified. Actual cache refusal cause
still unknown; do not infer missing libSystem from dyld's fallback message.
Native-header probes for A6Input.c and dyld_diag.c pass. Existing core BSD units
need Apple Clang allocator builtins and macOS SDK (local iOS SDK lacks MAP_32BIT);
validate those and the full link in Actions. SMP remains cpus=1 in all images.

bc1271e: all Actions 39420499935 passed, including native Apple Clang BSD/IOKit
and final NOUNDEFS link. Verified kernel SHA256
5184d5e43cffa55728a87ea8cb32cbf506692fe81f558440b0d322a4b2ca18dc.
Latest verified CPU0-only image (fastboot boot accepted, screen result pending):
build/verified-bc1271e/images/xnu-8796-userdata-cpu0-boot.img, 17094656 bytes,
SHA256 d768ef87c2c7f896d01b10fd96ac915d210c1d94cb0a402687248655567a36dc.
CRC/version/root/CPU limit validated; actual native early-stage disassembly
still uses three PC-relative ADRP/ADD strings. Linked input status and dyld
diagnostics symbols/strings present. User returned the phone; loader hfs-map-v2
verified, SHA256 and full image checks repeated. Fastboot accepted this exact
image in 0.491 s (send 0.380 s, boot 0.078 s). Private log:
artifacts/boot-bc1271e-cpu0.private.log. No flash, UART or USB-network startup.
Screen result pending: ask for `A6PLTE BOOT DIAGNOSTICS (CPU0)`, S6 command/reg/value,
dyld first failure and last signature. No cache cause asserted yet.
