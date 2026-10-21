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
Hardware result: user reports `signature dyld_shared_cache_arm64 errno 22
coverage -1 / 114409472` (signature offset 0x6d1c000). This is F_ADDFILESIGS_RETURN
failure before coverage copyout, not yet a proven hash mismatch. S6 probe reg/value
still not provided.

Next candidate removes the BSD userdata strategy's arbitrary rejection of
buffers >64 KiB. The existing slice checks the WHOLE request against validated
userdata before the existing one-sector-at-a-time SDHCI transfer; readonly/GPT
checks and physio's 64-KiB cap remain intact. A native-strategy ASan/UBSan test
reproduces large 1-MiB reads/writes, rejects a write that crosses the slice before
any sectors are changed, and checks buffer guards/readonly/EOF/raw cap. Input
and slice code unchanged. This is a demonstrated driver bug, not confirmation
that it caused this specific signature EINVAL. Signature diagnostics now retain
the fcntl stage (read/allocate/validate/coverage), plus exact cs_blob rejection
stage, page shift, limit and coverage. Preserve native signature verification.

665a2d5 pushed; all local tests pass, including the actual BSD strategy test.
Actions 39445871601 initially queued the macOS job, now building. Background
download/package watcher exec session 45300 will place the full native image in
build/verified-665a2d5/images/xnu-8796-userdata-cpu0-boot.img once ALL CI jobs pass.
Check that receipt first if it is ready by the time the phone returns.

User insists on an actual fix immediately. A ready temporary image applies the
same source fix to verified native bc1271e: NOP exactly the independent count>
65536 rejection branch at KVA fffffff00741ff84 (file offset 41bf84), original
instruction 540007e8 -> d503201f. Strict original SHA256, surrounding negative
LBA/alignment instructions, slice call and symbol addresses verified; every
other kernel byte unchanged. The whole-request a6_slice_io bounds, read-only
attributes, GPT checks and raw physio cap remain. CPU0 only, no rootfs, UART
and USB network off. CRC/payload/profile checks pass. This hotfix does NOT add
the new granular signature stage logs from 665a2d5, and its symbol addresses
still match bc1271e. Do not describe it as a new full-source CI build.
Ready image: build/hotfix-bc1271e-largeio/xnu-8796-userdata-cpu0-largeio-boot.img,
SHA256 8724bb1b8b1cd842e1fcccb4e65da14082f9aa414b5baa02f420c7d0d2cf2004.
Kernel: build/hotfix-bc1271e-largeio/kernel.a6plte, SHA256
46d2c8ddfa7957a49428aa7f2ed8309704938b3caa71f88919d3304acede8e15.
Receipt in same directory. Not booted yet: fastboot empty; hardware-reset
readiness question already pending. Load a verified ready image as soon as the
phone returns; no new pasta authorization required. The driver bug is fixed,
but whether it resolves this actual signature failure still needs hardware.

Full native 665a2d5 has now PASSED all Actions 39445871601, downloaded and
packaged. USE THIS image instead of the never-booted binary hotfix above:
build/verified-665a2d5/images/xnu-8796-userdata-cpu0-boot.img, 17094656 bytes,
SHA256 b0992daac96d59239bca527b783c2bd6345033e66a431ac9f54d3b397de7c351.
Kernel build/verified-665a2d5/kernel/kernel.a6plte, SHA256
3ce28c0d29741ec701af6186d79f377f7c1db63266a58fc2ef37691da96174a2.
Actual native strategy disassembly verified: 64-KiB rejection removed, checked
a6_slice_io still called. Full image checks passed; receipts in verified path.
Watcher session 45300 completed successfully. User returned the phone; the full
native 665a2d5 image above was SHA256/CRC/profile checked again, loader hfs-map-v2
verified, and fastboot boot accepted it in 0.475 s (send 0.379 s, boot 0.078 s).
Private receipt artifacts/boot-665a2d5-cpu0.private.log. Screen result pending:
ask last lines, `dyld blob failure` and fcntl stage after last signature if it
fails again. The binary hotfix was never loaded and is superseded. SMP off,
no flash/UART/USB-network startup. No new pasta permission required.

User now explicitly requests persistent, incremental on-disk 16K-to-4K hash
conversion and reports `vm shared region start address failed`, then says an
error started at “44” of `dyld_shared_cache_arm64.*`. Exact filename/errno not
provided; an async question for the last signature/blob/map2 lines is pending.
Do not assert the root cause from “44”. The previous prohibition on file changes
does not block the explicitly requested derived cache files on userdata; do not
replace the user's userspace, format or write other partitions.

New source: cs_cache.c append-only, independently SHA256-checked records per
4 MiB of verified source, HFS F_FULLFSYNC, resume through the last intact record.
cs_cache_vfs.c confines `/.a6cs4k-v2-<key>` files to the userdata root, root uid,
0600, one link, regular file, no symlinks/cross-mount lookup; identity binds full
CodeDirectory + inode/size/mtime/ctime/base/hash geometry. Source changed during
verification causes ESTALE and invalidates the checkpoint. Cached tables are
trusted root-owned derived metadata, not cryptographically authenticated against
a malicious root; document this rather than claiming checksums are signatures.
Actual fault pages remain hash-checked; source/signature validation is retained
on misses. Cache errors/full disk fall back without publishing an unchecked
partial table. The first run necessarily computes unsaved portions again.

VFS used to mount every root read-only before launchd; it now mounts only an
explicitly writable, selected userdata HFS root writable from the start, so
checkpoint creation works before dyld. GPT readonly and a6_userdata_rw=0 remain.
An empty native shared-region probe returns KERN_INVALID_ADDRESS/ENOMEM by design
before the first map2. Preserve that error and real mapping, reduce only the
misleading ERROR trace for this normal case, retain the actual last check/map2.
This does not establish or fix an unreported mapping refusal. SMP stays cpus=1.
New ASan/UBSan tests exercise real journal/core and VFS adapter, all torn final
record lengths, corruption, resumed prefix, source changes, read-only reuse,
ENOSPC/fsync failure, permission/link/mount checks and balanced resources. Existing
signature/fault and full host tests pass. Native cs_cache.c/dyld_diag.c probes
pass; cs_cache_vfs uses real kalloc_type Apple builtins and must pass native CI.

ba06ed0: ALL Actions 39470889999 passed, including actual Apple Clang VFS/cache
objects and NOUNDEFS link. Downloaded kernel SHA256
aa13d33bdf58d8ac1d191116c7fc0c85a0aa4ab1fa93821bbd23ff8cd7855e0d.
Verified image build/verified-ba06ed0/images/xnu-8796-userdata-cpu0-boot.img,
17094656 bytes, SHA256
8d197114953521d6be24710458a801d8bd209e5f20e3aceba95eb4d2bd6acbce.
Expected loader is getvar `a6plte:xnu-loader` -> hfs-map-v2, NOT the empty
standard version-bootloader var. Actual ba06ed0 image boot accepted in 0.484 s
(0.376 send + 0.078 boot); private log artifacts/boot-ba06ed0-cpu0.private.log.
An async question for checkpoint-saving line and final dyld signature/blob/map2
is pending. The user had already reset before the exact “44” error was recorded.

User supplied physical touch failure: cmd 21, reg 02000018, value 00000040.
This is a polled QUP OPERATIONAL timeout with OUT_FULL, not an S6 firmware
integrity response. Probe 0x52/0x55 succeeded before 0x21. Source had reset the
mini-core as soon as RX bytes were visible without waiting for I2C BUS_ACTIVE
to clear (STOP may still be in progress). Also waited only MAX_OUTPUT_DONE on
short FIFO writes, although QUP OUTPUT_SERVICE can precede it. Fix adds bounded
idle-before-reset, FIFO SERVICE completion, read-response completion, and wait
for I2C master-gen readiness after selection. Own HID stays own; no Sweet HID.
Regression models delayed physical STOP and reproduces the exact cmd21/reg18/40
failure with the prior actual driver. Fixed actual driver passes it and a
SERVICE-only (lagging DONE) transfer, ASan/UBSan and native A6Input.c header probe.
This demonstrates source defects, not proof of working touch on the phone.

333bb5d: ALL Actions 39473267592 succeeded (native compile, NOUNDEFS link, host
tests and packaging). Verified downloaded kernel SHA256
14852edc5624f43140ab6dc6d752f6144b5ee2be6408ef72caa7782976fcedb6.
READY image: build/verified-333bb5d/images/xnu-8796-userdata-cpu0-boot.img,
17094656 bytes, SHA256
ffeb92cb7e28118b3cbe5f940bb1d3eecca734be518853381bd0186afa09d6ed.
Image CRC/root/CPU0/USB/BootArgs profile checks passed, receipt next to kernel;
linked native cache open/save/close, writable-root and input symbols verified.
Includes both persistent hash conversion and own I2C completion fix. NOT BOOTED
yet: fastboot empty after ba06ed0 activation. Readiness question pending: return
from the current run to lk2nd after preserving final error lines if any. A second
pending question asks whether ba06ed0 shows checkpoint saving and final dyld
signature/blob/map2. No new pasta permission needed. Do not flash boot or LK.

User returned to lk2nd. Native 333bb5d image above was SHA256 checked again,
full CRC/BootArgs/root/CPU0/USB profile revalidated, and expected loader
`a6plte:xnu-loader=hfs-map-v2` verified on the expected device. Fastboot boot
accepted it in 0.479 s (0.372 send, 0.078 boot). Private receipt:
artifacts/boot-333bb5d-cpu0.private.log. This is now the latest PHONE BOOTED
image, no flash. Screen result pending: async question asks S6SY761 ready/probe
status, checkpoint reused/saving lines, and final dyld error if it stops.
Do not infer physical touch or successful launchd from fastboot's OKAY.

Latest 333bb5d hardware result: journal start=end=0x200 reset message, then
`memmove_chk object size check failed ... (16 < 32)`, subrs.c:725, caller
`0xfffffff007297cd4`. Exact native disassembly places that caller after the
panic call in ___memmove_chk, not at the original HFS copy. Both buildrecord
and catrec_update in Apple's hfs_catalog.c pass a 32-byte copy into 16-byte
userInfo (adjacent finderInfo holds the other half). The actual strict native
guard reproduces this exact failure with the original catalog source. The fix
copies userInfo/finderInfo separately on create/update/read, and zeroes dataFork
and resourceFork individually; no fortify bypass or on-disk format changes.
tests/test_hfs_finderinfo.py uses the real Apple disk structs, actual catalog
functions and extracted XNU __memmove_chk/__memset_chk, with ASan/UBSan. Both
positive and original-source negative controls passed; 32 Finder bytes, six
inode types, 2-byte alignments, both forks, fixed disk sizes, guards and stale
inode rejection checked. Aggregate HFS patch updated, full CI/hardware pending.
This panic must be fixed before on-disk checkpoints can be evaluated; it does
not establish the prior shared-region/map2 refusal's cause. Keep CPU0 only.

HFS fix ad7c960 passed native Apple Clang and packaging, but its Linux test job
missed uuid/uuid.h. Follow-up 2a53d3c adds uuid-dev to the runner; source code is
unchanged. ALL Actions 39487558036 now pass. Actual linked HFS create/update/read
functions no longer call the failing checked 32-byte copy; Apple's compiler
emits independent 16-byte field accesses. Strict ___memmove_chk remains intact.
Verified kernel: build/verified-2a53d3c/kernel/kernel.a6plte, SHA256
6463618921f000cef2bc8d0b0cf911d986d453e8ade0bc9cec7632668d13fb51.
Verified image: build/verified-2a53d3c/images/xnu-8796-userdata-cpu0-boot.img,
17094656 bytes, SHA256
0cf772962f4f1688b67ba019cfca84d1ef13c28da1c8c743684762cae6c54e4a.
User returned phone to lk2nd; expected device and hfs-map-v2 loader verified,
kernel/image SHA256 rechecked, fastboot boot ACK in 0.485 s (send 0.373, boot
0.078). Private log artifacts/boot-2a53d3c-cpu0.private.log; image/boot receipts
in build/verified-2a53d3c. This is now the latest PHONE BOOTED image, not a flash.
CPU0, userdata HFS root/launchd, UART forbidden, USB network disabled unchanged.
Screen-result question pending: did HFS pass, did checkpoint save/reuse start,
and exact panic reason/caller if it fails again. Do not infer success from ACK.

Hardware 2a53d3c passed the HFS fortify failure and all reported signatures:
`.42.dyldlinkedit errno 0 coverage 333447168/333447168 (return coverage)` and
its 16-KiB header mmap errno 0. Actual failure is map2: 44 files, 52 mappings,
errno 1 (EPERM), NOT a failed signature. User also recalls a
vm_shared_region_map_file message but not its exact text/kr. Do not assert a
single EPERM cause yet. The macOS CONFIG_CSR profile requires SF_RESTRICTED;
a board-limited iOS-style cache rule now accepts only regular root-owned arm64
cache files in known cache directories on the validated userdata root, same
root vnode/mount. Native MAC, descriptor, ownership, signature coverage and
VM protection checks remain; no global CSR setting or file flags are changed.
Actual native owner/CSR/directory policy host test reproduces baseline EPERM
without SF_RESTRICTED and passes the fix/rejections/balanced vnode refs. Native
dyld_diag.c header probe and full host suite passed. If the fault is in VM,
retain the actual VM kr and failing fd/index/VA/size/offset/protections and
repeat them at the final PID1 framebuffer report. No fake map2 success.

S6SY761 still physically failed cmd21/reg02000018/val40 with 2a53d3c. New own
input fix leaves FIFO SERVICE unmasked (0x300 masking is BAM/DMA setup), and
does not accept stale SERVICE/DONE while OUT_NOT_EMPTY or OUT_FULL is set.
Sensor startup follows application's boot event -> boot status -> touch
function -> ID -> panel info -> firmware integrity -> clear/sense-on order;
a warm boot may already have consumed the boot event. No firmware flashing,
PMIC power/reset writes, UART or Sweet HID. Real-driver ASan/UBSan test now
covers stale SERVICE with queued output, bounded completion, old delayed STOP
and lagging DONE, startup order and existing contact/button/HID tests. Physical
touch and actual map2 success remain unconfirmed. CPU0/USB-off unchanged.

Latest user constraint: ONLY FIXES are authorized, no new diagnostic-only changes
or test boots. Removed the newly added setup-stage/VM-mapping diagnostic calls,
state buffers and final-screen messages before loading any new image. Preserve
existing framebuffer logs. The 125e29e run was started before this constraint;
do not cancel it, but do not load its diagnostic additions. The follow-up image
contains only the bounded userdata cache policy and own input corrections,
with regression tests. No new map2-success claim until actual hardware passes.

80a9d97: ALL Actions 39564909222 passed, native Apple Clang/NOUNDEFS and full
host regressions/packaging. Verified kernel SHA256
87f0e7214b9043a8f0761083212e7d65da389901232378593551053498cf2708.
Image build/verified-80a9d97/images/xnu-8796-userdata-cpu0-boot.img,
17094656 bytes, SHA256
fb79ecffaff5054645d7cbe00c6588c9c483101b9feb9780adf2ea46c37761f8.
Native symbols confirm a6_dyld_root_cache is linked and new diagnostic functions
and messages are ABSENT. Kernel/image SHA256 rechecked, expected device and
hfs-map-v2 verified. User returned phone; fastboot boot accepted this exact
fixes-only image. Private receipt artifacts/boot-80a9d97-cpu0.private.log;
image/boot receipts in build/verified-80a9d97. This is latest PHONE BOOTED image,
not a flash. Actual touch/map2 result pending, not inferred from OKAY.
The user only allows fixes: do not add new diagnostic-only code or images.
Keep CPU0, userdata/launchd, UART forbidden and USB networking disabled.

User supplied IMG_3488.HEIC after the 80a9d97 boot. This is historical evidence,
NOT a result for that image: EXIF DateTimeOriginal is 2026-10-20 16:35:00 and
visible caller 0xfffffff007a770fc matches exactly bc1271e's
_proc_prepareexit.cold.2+0x7c (return from panic_with_options). The same call in
80a9d97 is 0xfffffff007a78bfc. Photo shows .01 signature errno22 coverage -1 /
114409472, no signature-stage suffix, 1 signed, map2 not reached, S6 cmd21
reg02000018 val40. Do not revert current code or diagnose the latest build from
this older photograph. Latest actual image remains 80a9d97 boot ACK; current
physical touch/map2 result still pending. Photo converted locally for reading
only; never add the image to Git or use UART.

IMG_3490.HEIC is current (EXIF 2026-10-21 13:18:29). Native launchd has begun
executing and prints its own libxpc/launchd journal, so this is beyond the old
dyld cache refusal. Kernel data abort PC 0xfffffff0078b1a30, LR
0xfffffff007be1d7c, ESR 0x96000005, FAR 0x28, X22=0 matches the actually booted
80a9d97 SHA1Init/sha1_init+0x20: load g_crypto_funcs (NULL), then ccsha1_di at
offset 0x28. No external corecrypto kext is loaded; existing SHA2/MD5 fallbacks
did not cover legacy SHA1. Add real scalar SHA1 ccdigest descriptor and route
legacy init/update/final plus ccsha1_di() to it only without a provider. Keep
native ccdigest streaming/finalization, SHA1_CTX ABI and provider callbacks.
No hash/signature checks removed and no new diagnostic-only code. All host
tests pass, including 478 actual-wrapper/actual-ccdigest vectors, null/present
provider, million-byte input, padding/alignment/chunks/guards and Final_r.
Original wrapper negative control reproduces the NULL dereference. All three
changed native units compile against real generated 8796 headers. Native full
link/build and hardware result pending. CPU0, USB off, userdata/launchd and
UART prohibition unchanged. Do not claim physical touch from this photograph.

aa5824e: ALL Actions 39585752726 passed (Apple Clang, NOUNDEFS, host regressions
and packaging). Verified downloaded kernel SHA256
71aabac8a533922bed09deb44c21e76951c653318a1f7ec303036c66ef077673.
Native linked ccsha1_ltc_di descriptor has the real 20/20/64-byte output/state/
block sizes, SHA1 OID and scalar compression, using Apple's ccdigest_final_64be.
READY image build/verified-aa5824e/images/xnu-8796-userdata-cpu0-boot.img,
17111040 bytes, SHA256
94894df4eb41bfd76dca060c0c48b0a2b1d84d96b12085b54507d6227f9495ba.
Source/run/archive/kernel/image receipts and complete CRC/profile checks pass.
NOT BOOTED yet: expected phone absent from fastboot. Async hardware-reset
readiness question pending. Load this verified image when the phone returns;
no new pasta approval needed. No flash, new diagnostics, UART, USB networking
or SMP. Latest actual phone boot remains 80a9d97 until a new boot ACK.

User returned the phone, then reconnected USB when the host saw no USB device.
Native aa5824e image above was rechecked (kernel/image SHA256, complete CRC,
CPU0, userdata/launchd, USB off) and expected phone/hfs-map-v2 verified.
fastboot boot accepted this exact image: send 0.382 s, boot 0.078 s, total
0.478 s. Private log artifacts/boot-aa5824e-cpu0.private.log; boot receipt in
build/verified-aa5824e/boot-receipt.json. aa5824e is now latest PHONE BOOTED
image, not a flash. Actual framebuffer/launchd result pending; no new hardware
success or physical touch claim from fastboot ACK. Keep fixes-only constraint.

IMG_3491.HEIC (2026-10-21 13:56:17) is the aa5824e hardware result. It confirms
shared region 44 files / 52 mappings errno 0, cache mapped at 0x1b8900000,
native launchd journal and the first mount-phase-1 task. SHA1 abort is passed.
New panic: `userspace panic: boot task is not a platform binary (mount-phase-1,
/sbin/mount)`, caller 0xfffffff007a7d1c8 = aa5824e panic_kernel+0xe0. The board
has no AMFI provider or MAC signature hook to set CS_PLATFORM_BINARY: native
CodeDirectory initialization masks that kernel-only flag and leaves platform
status zero, which propagates through cs_blob and Mach-O loading to csops/tasks.

Fix: the already-registered board compatibility MAC policy adds the native
vnode_check_signature callback. Only without AMFI, on the explicitly selected
userdata root mount, for regular root-owned system-path files with a valid,
non-ad-hoc CodeDirectory and nonzero native platform marker, it sets the
platform flag. This trusts the user-prepared OS root; it does NOT authenticate
an Apple CMS chain. Native page hashes/validation and other MAC failures stay
active, no entitlement/provider objects or new diagnostics added. User files,
foreign mounts/roots, missing marker/valid flag, ad-hoc signatures, missing
attributes/path failures are not promoted. Native provider status is untouched.
Actual callback plus native cs_blob/load-result propagation pass ASan/UBSan;
negative control reproduces non-platform status with the old absent callback.
Full host suite and native compat.c header probe pass. Full CI/link and hardware
pending. User has already returned phone for this fix; check fastboot and load
verified image as soon as ready, without new permission. CPU0 and USB-off remain.

9eabb12: ALL Actions 39590206698 passed (native Apple Clang/NOUNDEFS, host
regressions, packaging). Verified native kernel SHA256
5602b3d1805c34e5001da9e42dfb31402fb6a87821887d56f21ebd7ecda084a3;
linked platform_signature and ccsha1_ltc_di confirmed. Latest image:
build/verified-9eabb12/images/xnu-8796-userdata-cpu0-boot.img, 17111040 bytes,
SHA256 bb292af945185361c6260a5e04499f84bc0c8a5ecfac96c4bd22df7da23620a9.
Full CRC/profile and receipt hashes verified; expected phone/hfs-map-v2 checked.
User already returned phone, fastboot boot accepted exact image automatically
after all CI passed: send 0.378 s, boot 0.078 s, total 0.476 s. Private log:
artifacts/boot-9eabb12-cpu0.private.log; image and boot receipts beside kernel.
This is latest PHONE BOOTED image, not a flash. Actual mount-phase-1/launchd
screen result pending. Keep CPU0, USB disabled, no UART or new diagnostics.

IMG_3492.HEIC (2026-10-21 14:19:06) shows 9eabb12 still stopping at the SAME
non-platform `/sbin/mount` boot task, despite successful cache map2 and launchd.
Do NOT claim that the first platform-policy fix passed on hardware. The actual
failing predicate is not printed, and the photo cannot distinguish marker,
ad-hoc or vnode-path checks. The user returned the phone to lk2nd, then explicitly
steered: **only work on the kernel**. Stop userspace/raw-HFS inspection and broad
file searches; do not change prepared files. Continue with XNU source, its tests,
CI and userdata-root kernel packaging. No further permission needed to boot.

Kernel correction removes the unsupported requirement for an Apple platform
marker/non-ad-hoc signature on the already trusted selected OS root. Valid
CodeDirectory/page checks, root uid, regular-file/same-root mount, known system
paths and native MAC denials stay in force. HFS hardlink cached inode paths are
handled by native exec_save_path data, with matching imgp/ni_vp, original namei
root, bounded strings/no traversal and fresh same-vnode lookup. Policy is called
after successful native mac_vnode_check_signature, not through a pretend AMFI.
Revalidation also updates immutable cs_blob platform fields using native RO
updates, since signatures may be attached before the exec identity is available.
No new logs, diagnostics or userspace changes. Native header probes and regression
tests cover actual helper, post-MAC gate, cs_blob/load-result and revalidation,
including re-signed zero-marker code, HFS alias/path cache failure, vnode/root
identity, MAC/provider failures, traversal, bounds and balanced vnode references.
The actual previous callback negative control rejects a valid re-signed system
task, reproducing that source defect. Hardware cause/result still require next
fixes-only image. CPU0, UART prohibition and USB networking off unchanged.

c0e8470: ALL Actions 39595600048 passed (actual Apple Clang/NOUNDEFS link,
full host regressions and packaging). Kernel SHA256
224b4b8d0bb950d256bb8506ffb2b588af7411e213f432fdd8cbb369cbd1c24d;
new a6_platform_signature and prior real SHA1 descriptor linked. Image:
build/verified-c0e8470/images/xnu-8796-userdata-cpu0-boot.img, 17111040 bytes,
SHA256 9fc361dd188e37598dea90840fdb335df95c50b35fa803509e47e04c93fad74c.
Source/archive/kernel/image hashes, complete CRC/CPU0/userdata/USB-off profile
and expected phone/hfs-map-v2 verified. User had already returned the phone;
fastboot boot accepted this exact image: send 0.379 s, boot 0.079 s, total
0.476 s. Private log artifacts/boot-c0e8470-cpu0.private.log; image and boot
receipts in build/verified-c0e8470. This is latest PHONE BOOTED image, not a
flash. Actual mount/launchd result pending. Prepared userspace was not modified.
Keep the user's kernel-only scope; no further userspace inspection/changes.

Latest c0e8470 hardware result: SAME `userspace panic: boot task is not a
platform binary`. User explicitly requests **bypass/remove that check**.
Keep this kernel-only: do not patch launchd or suppress panic syscalls. The
prepared OS root now supplies platform compatibility status without uid/path/
CodeDirectory marker restrictions. Regular vnode + explicitly selected userdata
root mount + no AMFI are the only board bounds; all code on that OS root may
receive platform status, including unsigned/re-signed files. This is the user's
requested development bypass, not Apple authentication or a CS_VALID grant.

Native F_GETSIGSINFO checks the file BEFORE exec may have attached a cs_blob;
old native code returns ENOENT there. Cover both zero and native wildcard -1
offsets before the blob lookup. Keep copyin/out, fd-type, vnode lifecycle and
other request errors. Also cover blob/proc/file platform getters and loaded-task
status, so csops and exec agree even without signature metadata. Native Mach-O
failure, code-page hashes, signature validity bits and other MAC failures stay
active; other mounts and an actual AMFI provider retain native behavior. No logs,
new diagnostic image or userspace edits. Actual upstream F_GETSIGSINFO negative
control reproduces ENOENT; new native-case ASan/UBSan regressions cover no-blob,
-1, process/fd/task views, flags, providers, other mounts, copy errors and balanced
refs. Full host suite passed. kern_cs.c/compat.c native probes pass; large BSD
units require actual Apple allocator builtins and must pass Actions. User already
returned phone for this new kernel; boot once the verified image is ready.

7538fd7: ALL Actions 39598057211 passed (native Apple Clang/NOUNDEFS link,
full host regressions and packaging). Verified native kernel SHA256
58b7f01445fe5c2760c9e2cae4cf2c1d1dc7858aa03c4d285583880ae654a249;
linked a6_platform_file, a6_platform_signature and real ccsha1_ltc_di confirmed.
Image build/verified-7538fd7/images/xnu-8796-userdata-cpu0-boot.img,
17111040 bytes, SHA256
0e06d2f4751f49e3415e6a5ec59b68dbf66eea710b10a147ea7755a1f199ae7d.
Source/archive/kernel/image hashes and full CRC/CPU0/userdata/USB-off profile
checked; expected phone and hfs-map-v2 verified immediately before boot.
User had already returned the phone for this bypass. fastboot boot accepted
this exact image: send 0.374 s, boot 0.078 s, total 0.471 s. Private log
artifacts/boot-7538fd7-cpu0.private.log; image and boot receipts beside kernel.
This is latest PHONE BOOTED image, not a flash. Actual launchd/mount-phase-1
hardware result pending; async screen question asked. Do not claim the panic
has passed based on fastboot ACK. No userspace changes or inspection, new
diagnostics, UART, USB networking or SMP. Preserve kernel-only/fixes-only scope.

7538fd7 hardware: user reports `failed to get a codesigning identity for a boot
task errno 2`, after the prior platform-binary refusal. User has already returned
the phone to lk2nd for this fix. Do not ask for readiness again if fastboot sees it.
Concrete source defect: cs_blob_init_validated and revalidation initialize flags
with CS_ALLOWED_MACHO | CS_VALID, which excludes process-only CS_SIGNED. No AMFI
provider sets it, and the board callback previously added only PLATFORM_BINARY.
Native load_code_signature/exec preserve the missing bit; cs_identity_get then
returns NULL before looking at the actual stored identifier, and native
CS_OPS_IDENTITY returns ENOENT. Correct the existing board signature callback
to set CS_SIGNED only when a real cs_blob/csb_cd exists and native cs_flags is
VALID, after native MAC success and within the same selected-root/no-AMFI bounds.
No synthetic identifiers, CS_VALID grants, TeamIDs, entitlements, panic suppression,
new logs or userspace changes. Initial attachment and native RO revalidation both
propagate the bit. Actual native exec/identity/blob-lookup/csops-body ASan/UBSan
regression reproduces ENOENT with a real com.apple.mount CodeDirectory and fixes
it while preserving all signature bytes, native buffer ABI/errors, flags and
provider/root/unsigned/invalid rejection. Native compat.c header probe passed.
Full host suite passed. Native CI and exact-image hardware verification are next.

a05051c: ALL Actions 39600356778 passed (native Apple Clang/NOUNDEFS link,
host regressions and packaging). Verified native kernel SHA256
6f859bcaf6ad81771c271fb91673c15674052a0068d90f528569ab9e8fdc187f;
linked platform helpers, cs_identity_get and real SHA1 descriptor confirmed.
Image build/verified-a05051c/images/xnu-8796-userdata-cpu0-boot.img,
17111040 bytes, SHA256
ec4ef4c89d74688cda1f83745efaa807cab276a34f454e45de72a77b8bc02c21.
Exact successful CI source/archive/kernel/image hashes, full CRC/CPU0/userdata/
USB-off profile and expected phone/hfs-map-v2 checked. User already returned
the phone. fastboot boot accepted this exact image: send 0.372 s, boot 0.078 s,
total 0.469 s. Private log artifacts/boot-a05051c-cpu0.private.log; image and
boot receipts in build/verified-a05051c. This is latest PHONE BOOTED image,
not a flash. Actual boot-task identity/launchd result pending; async screen
question asked. Do not infer success past the previous panic from boot ACK.
Keep kernel-only/fixes-only, CPU0, no UART, USB networking disabled and no
inspection or modification of prepared userspace files.

a05051c hardware: user reports `failed to get boot manifest hash no such file
or dir`, after the boot-task identity failure. User already returned the phone
to lk2nd for this fix. The Apple DT's /chosen has no boot-manifest-hash or
boot-objects-path, so native IOGetBootManifestHash fails and kern.bootobjectspath
returns ENOENT. Kernel-only correction in A6PLTEPlatformExpert::start publishes
boot-manifest-hash after native DT initialization and before board services/
BSD launch. There is no Apple Image4 manifest in this boot: the value is a
standalone compatibility identity, SHA384(ASCII `A6PLTE standalone boot identity
v1` without NUL || actual linked LC_UUID's 16 bytes). It is stable for that
image across reboots, contains no entropy/address/time data, and is NOT Apple
authentication or a matching userspace/preboot manifest. No files are inspected,
created or modified. Preserve an existing 20/48-byte OSData firmware hash; reject
malformed data, missing UUID or failed publication. No new logs/diagnostics.
Actual helper/native IOGetBootManifestHash/native ARM sysctl-body ASan/UBSan
tests reproduce ENOENT, verify SHA384 with a known UUID, native raw/hex reads,
stable/changed UUID, firmware preservation, error handling and balanced refs.
Full host suite passed. Package checker now requires one nonzero native LC_UUID.
Local C++ header probe hits existing Apple allocator builtins unavailable in Linux;
do not add fake builtins or header stubs, validate the actual TU with Apple CI.
CI/native link and exact-image hardware verification are next. CPU0, USB-off,
UART prohibition and kernel-only/fixes-only scope remain.

ae9c607: ALL Actions 39602773339 passed (actual Apple Clang/NOUNDEFS link,
host regressions and packaging). Verified native kernel SHA256
e76acb5ae3a37babdc57f1bc658921508ec18f70869695f74cc85a46cac46004.
Linked UUID/SHA384, prior real identity/platform helpers and SHA1 confirmed;
standalone hash domain present. Image:
build/verified-ae9c607/images/xnu-8796-userdata-cpu0-boot.img, 17111040 bytes,
SHA256 62b5956f605f571ecc90162b5f1f106328de462523aef972dce3f898fd9acc64.
Successful source/archive/kernel/image hashes, nonzero unique LC_UUID, full CRC/
CPU0/userdata/USB-off profile and expected phone/hfs-map-v2 verified. User already
returned phone, fastboot boot accepted this exact image: send 0.381 s, boot
0.078 s, total 0.479 s. Private log artifacts/boot-ae9c607-cpu0.private.log;
image/boot receipts in build/verified-ae9c607 (including expected standalone
boot_identity_sha384). Latest PHONE BOOTED image, not a flash. Actual passing
boot-hash query/launchd result pending; async screen question asked. No new
hardware progress inferred from fastboot ACK. No userspace inspection/edits,
new diagnostics, UART, USB networking or SMP.

IMG_3493.HEIC (2026-10-21 15:57:04) is ae9c607 hardware: printed Preboot hash
3C35AD9D...4432CB7E exactly matches its image receipt, proving hash retrieval.
/sbin/mount and mount_hfs run, root is /dev/a6userdata on / (hfs, journaled).
Fatal next: firmware source /private/preboot/<hash>/usr/standalone/firmware ->
/usr/standalone/firmware returns ENODEV 19; mount-phase-1 exits 74 and launchd
requests panic. vfs_conf has BINDFS disabled in the board's macOS-derived profile
although Apple ships its native implementation. Enable bindfs in that profile
and verify its three native sources/option in configuration and symbols in the
complete-image checker. No fake mount success or panic/exit suppression.

Board-only bindfs entitlement compatibility allows root processes whose text
vnode is on the explicitly selected userdata root, only without AMFI. Actual
native bindfs mount/lookup/refcounts/read-only/nosuid flags stay in use. On ENOENT
only, recognize the EXACT 48-byte current boot hash's uppercase Preboot firmware
path and the exact target /usr/standalone/firmware on a directory covered vnode
belonging to the root mount. Use that already-existing covered directory as the
real lower vnode for read-only bindfs. Take its iocount directly; never re-lookup
the target while its mount is in progress (avoids waiting on this same mount).
No directories/files/firmware are created, read from the host or modified.
Prepared real Preboot sources and non-ENOENT errors retain native behavior.

Photo also reports `jnl: flushing fs disk buffer returned 0x19` = ENOTTY 25:
userdata implemented only DKIOCSYNCHRONIZECACHE, while HFS uses DKIOCSYNCHRONIZE.
Add the native request handler with full-range/overflow/options/reserved-field
bounds, serialization and actual a6_emmc_flush, including stronger full flush
for a barrier request. Preserve actual card errors and all partition/write caps.
Native-helper/permission/lookup integration ASan/UBSan tests cover real lower
vnode, wrong paths/hashes/roots/providers, reference and error behavior. Actual
device_ioctl negative control reproduces ENOTTY; tests cover full/barrier flush,
invalid/overflow ranges, options, refs/lock, timeout/offline and legacy dispatch.
Full host suite passed; native compat.c header probe passed. Apple CI/native
link and hardware verification are next. Phone reset-readiness question pending.
Keep kernel-only/fixes-only, CPU0, no UART and USB networking disabled.

ada2366: ALL Actions 39606173594 passed (native Apple Clang/NOUNDEFS link,
host regressions, packaging). All three native bindfs units compiled and linked;
native bindfs vfsops/vnodeops, board gate/fallback, identity/hash and SHA1 symbols
verified. Kernel SHA256
80949a6fb44386266ca970f639bd2d97fc7720fb333e558ec0dfc64068a5d3a6.
Image build/verified-ada2366/images/xnu-8796-userdata-cpu0-boot.img,
17111040 bytes, SHA256
4d57c506aeccf3e41aee8b7da3df2098dd7e30ad1c9487e4425cf96097839240.
Exact successful source/archive/kernel/image hashes, complete CRC/UUID/CPU0/
userdata/USB-off profile and expected phone/hfs-map-v2 verified. User returned
phone; fastboot boot accepted this exact image: send 0.379 s, boot 0.078 s,
total 0.479 s. Private log artifacts/boot-ada2366-cpu0.private.log; image and
boot receipts in build/verified-ada2366. Latest PHONE BOOTED image, not a flash.
Actual mount-phase-1 and journal-flush result pending; screen question asked.
Do not infer passing the old mount failure from fastboot ACK. No user OS files
were inspected or edited, no new logs/diagnostic images, UART, USB network or SMP.

IMG_3498.HEIC (2026-10-21 16:23:18) confirms ada2366 passed mount-phase-1:
the actual /usr/standalone/firmware bind mount appears in normal unmount output.
Next original failure is MobileKeyBag validation: systembag.kb missing WipeID,
validation -1, load -8, FATAL KEYBAG ERROR kb_load. Missing /options is also
reported. Final IOPlatformExpert Halt/Restart Timed Out panic follows MKB's
explicit recovery reboot request, not the initial failure. Do not suppress the
reboot/panic or manufacture a keybag/WipeID. Only kernel fixes remain authorized;
do not inspect or modify prepared userspace files.

Board expert now publishes empty OSData /defaults/no-effaceable-storage before
BSD/services: hardware capability is genuinely absent on this Qualcomm board.
MobileKeyBag's presence-only branch is documented by wh1te4ever/usbliter8-fun,
commit 84c0a31806c53bfe36eee6c669c671c0b2ced5be work-27.0b2/dt_patch3.py;
iOS16 qemu-t8030 hw/arm/xnu.c also sets it. Analysis is from another OS release,
so do not claim actual prepared userspace has passed MKB until phone evidence.
Do not add diagnostics mode or content-protect, fake /options/NVRAM, keybag
cryptography or keys. Existing flag preserved; missing node/publication failure
fails platform startup. ASan/UBSan regression executes actual board helper and
native IORegistryEntry OSData setter, covers missing versus empty property,
zero-length data, repeat boot/firmware preservation, unrelated metadata and
allocation/publication/refcount errors. Full host suite/native CI next. Phone
hardware-reset readiness question pending; boot verified image if fastboot sees
the expected phone without asking again. CPU0, USB-off, no UART, no flashing.

1909819: ALL Actions 39609959887 passed (Apple Clang/NOUNDEFS, full host
regressions, packaging). Actual linked kernel contains no-effaceable-storage;
prior bindfs/boot identity/platform/SHA1 symbols verified. Kernel SHA256
8c0779c65ed8fe2ff1fb97bcae95863a03a9c1e2881ad425f3f9985f1fbf162a.
Image build/verified-1909819/images/xnu-8796-userdata-cpu0-boot.img,
17111040 bytes, SHA256
4405ea7ab91264b9d44d1315aa77855c27a85374351a893819673dbdda7ec3ee.
Successful source/archive/kernel/image hashes, complete CRC/UUID/CPU0/userdata/
USB-off profile checked. Image receipt in build/verified-1909819. Phone was
absent from fastboot at packaging completion; NOTHING BOOTED OR FLASHED for
1909819. Latest actually booted kernel remains ada2366. Hardware-reset/readiness
question asked after concrete image ready. Boot this exact verified image once
expected phone/hfs-map-v2 are available, no extra permission required. Actual
MKB result unverified. Preserve kernel-only/fixes-only and prepared OS files.

1909819 hardware boot: user returned phone; expected phone and hfs-map-v2
verified, exact image SHA256 4405ea7ab91264b9d44d1315aa77855c27a85374351a893819673dbdda7ec3ee
sent via fastboot boot at 2026-10-21T13:48:07Z, ACKed in 0.484 s. Private log
artifacts/boot-1909819-cpu0.private.log, receipt build/verified-1909819/boot-receipt.json.
This supersedes the prior waiting status: latest PHONE BOOTED image is 1909819,
not a flash. Actual MKB result remains pending; screen text question asked.
Do not infer passing keybag validation from fastboot ACK. No userspace files
inspected/modified, no UART, SMP, USB networking or diagnostic-only changes.

1909819 hardware next stop: user reports `abort: unable to find amfi`, with
`Code: /System/Library/xpc/launchd.plist Sig: /System/Library/xpc/launchd.plist.sig`.
This identifies launchd_cache_loader's IOServiceMatching("AppleMobileFileIntegrity")
path, not a missing native AMFI function table. The board has no such closed
service/trust-cache authority. The helper has its own native
`launchd_unsecure_cache=1` boot switch: it opens/maps the launchd data cache
without the AMFI trust-cache query/detached-signature attachment. Enable only in
userdata boot profile. No userspace changes, fake AMFI service/trust verdict,
new logs, or native Mach-O/code-page hash changes. Complete image checker must
verify the switch in the actual compiled bridge. Reuse byte-identical successful
1909819 CI kernel for immediate bridge repack; record separate kernel and image
source provenance. New CI remains useful but no Apple kernel compilation is
needed for a boot-argument-only fix. Do not claim new Actions passed prematurely.
User also reports S6SY761 command 60 and an incomplete reg `20000...`; exact
register/value still unknown. Do not guess the bus fault or claim touch works.

88a09dd hardware boot: user explicitly reported PHONE_IN_FASTBOOT. Expected
phone/hfs-map-v2 checked; exact locally cross-compiled/checked bridge profile
with launchd_unsecure_cache=1 and unchanged successful 1909819 CI kernel
booted via fastboot boot at 2026-10-21T14:00:22Z, ACKed in 0.474 s. Image
build/verified-88a09dd/images/xnu-8796-userdata-cpu0-boot.img, 17111040 bytes,
SHA256 91c5dbea29a4bea364492dc342daf57c0ba6ca1f0fb9a72c38f62538d7c75b7c.
Kernel SHA256 8c0779c65ed8fe2ff1fb97bcae95863a03a9c1e2881ad425f3f9985f1fbf162a,
source 19098191f05403401f6b57e93e2cd6c3d60d0a1d, successful Actions 39609959887.
Local bridge AArch64 Clang -Werror and complete CRC/profile/Mach-O checker
passed. This does not claim new 88a09dd Actions passed. Separate kernel/image
provenance and boot receipts in build/verified-88a09dd; private fastboot log
artifacts/boot-88a09dd-cpu0.private.log. Latest PHONE BOOTED profile is 88a09dd,
not a flash. Actual launchd_cache_loader result pending; screen text requested.
No prepared userspace files inspected/edited, no fake AMFI service/trust verdict,
new diagnostics, UART, SMP or USB networking. S6SY761 command60 fault still
unresolved without complete register/value; do not claim physical touch works.

IMG_3456.HEIC (EXIF 2026-10-21 17:05:16) is the user's next hardware result
for booted 88a09dd profile. It shows successful iOS spawn messages for passd,
remindd, bluetoothuserd, WirelessRadioManagerd, navd, tccd, mediaremoted, biomed,
softwareupdated, runningboardd, aggregated, axassetsd, nanoprefsyncd and
contextstored. Existing process sampler 2/40 sees backboardd[56] (1 thread)
and SpringBoard[25] (3 threads). No panic, AMFI-cache-loader abort or fatal
keybag error is visible on this photo. This establishes progress beyond the
previous AMFI stop, not functional GUI, healthy daemon initialization or
system stability. Do not symbolize arbitrary shared-cache PCs from this image
without actual matching symbols, or inspect the user's OS files.

`Allowing spawn of iOS binary` is the existing native compatibility-path success
message in kern_exec.c, not an error. `A6PLTE SMP` is the old sampler log label;
cpus=1 still prevents AP starts. No kernel/boot-profile change needed merely
for those lines, and do not reboot this further-progressed session without a
concrete next fix. Own graphics services currently accept only A6 connection
ABI, not native private iOS IOSurface/IOMobileFramebuffer clients; native GUI
compatibility remains outstanding. Exact S6SY761 register/value and real touch
also remain unconfirmed. All 88a09dd Actions 39612534222 now independently
passed; the phone still uses the byte-identical 1909819 kernel in its locally
built 88a09dd bridge profile. No new diagnostics or userspace changes.

User now explicitly requests native iOS graphics compatibility, names ios-sweet
0046-sweet-iosurface-iomfb.patch as implementation reference, and wants ordinary
framebuffer logs hidden only after SpringBoard actually presents UI. Hardware
already returned to lk2nd: no extra readiness/permission question. UART remains
forbidden, cpus=1/USB-off/userdata launchd unchanged, no userspace inspection or
edits, no flash. User additionally identifies S6SY761 cmd60 reg02000018 timeout,
value unknown; do not guess or claim touch fixed.

Graphics implementation now adapts primary 0046 (commit
425b25102b6a9ee4b68fb2b9ca5d6a086b8a4116), cached-client sentinel contract from
0068, and 0056-style deferred presentation. Native IOCoreSurfaceRoot and
IOSurfaceRootUserClient: real shared buffers/state mappings, binary/XML property
creation, geometry/plane bounds, 0xa68 reply, ID lookup and Mach ports, lock/seed
traps, close/unmap, retained tasks, 64 MiB pool cap, parent descriptor retention,
reserved IDs while a send right retains its object, cached lookup replies -1
without duplicate mappings. Unsupported accelerators/shared events remain
unsupported. No new per-selector or creation diagnostics. Legacy A6 graphics
classes renamed and no longer published, preserving existing non-graphics
services. Native catalogue/ADT now publish /arm-io/disp0 display-subsystem with
1080x2220 canvas and Samsung compatible; AppleCLCD matches its actual platform
nub and exposes IOMobileFramebufferUserClient type0.

Framebuffer uses BGRA default IOSurface (not a wrongly advertised 32-bit mapping
of the 24-bit panel), real CPU composition/scaling/premultiplied alpha, actual
RGB888/XRGB scanout conversion, retained pending layer objects, 60 Hz software
notifications and default 10 Hz latest-frame presentation. Swap completion waits
for presentation; software power blanking and redraw retain panel setup. Only a
successful non-black full-canvas present by backboardd/SpringBoard hides ordinary
on-screen logs; memory log/ring still records them. Panic/early EL1 exception
forces console back and permanently stops graphics for that panic, never switches
to UART. Host ASan/UBSan suite passed, including 10000 extreme/clipped scanout
rectangles, channel/alpha/scaling vectors, DT/catalogue discovery and console
handoff/panic recovery. Local native C++ probes reach only the known unsupported
Apple allocator builtins, with no other API errors; Apple CI/NOUNDEFS link still
required before boot. Do not claim working iOS GUI until actual phone evidence.

f72b97a: ALL Actions 39621460260 passed (native Apple Clang/NOUNDEFS, complete
host suite and packaging). Actual IOSurfaceRootUserClient, IOCoreSurfaceRoot,
AppleCLCD/IOMobileFramebufferUserClient, RGB scanout, policy and panic-console
symbols linked and checked. Additional local ASan/UBSan actual-code tests passed
for 0xa68 reply/all 20 plane records, geometry, 64-bit narrowing, overflow and
opaque allocation. Promoted that test to test_iosurface_abi.py after CI; no native
code changed by that test promotion. Native kernel SHA256
e1c69bd3f2f2db4edbffe5f7f88981d8fd493aed3a7632fdd5d66975fe097d91.
Image build/verified-f72b97a/images/xnu-8796-userdata-cpu0-boot.img,
17209344 bytes, SHA256
9f2612aa91c2c38892c1eed6f9b2eb77b6e542ef9f23ab6ecd684affb62defd8.
Successful CI source/archive/kernel/image hashes, native symbols, complete CRC/
CPU0/USB-off/userdata profile and actual display-subsystem/canvas strings checked.
User had already returned phone; expected phone/hfs-map-v2 verified and exact
image fastboot boot ACKed at 2026-10-21T15:03:20Z in 0.470 s. No flash. Private
log artifacts/boot-f72b97a-cpu0.private.log, image/boot receipts in verified-f72b97a.
Latest PHONE BOOTED kernel/profile is f72b97a. Actual GUI result pending; asked
whether interface appeared, logs continue or panic occurred. Do not claim GUI
works from boot ACK or passing host mocks. Keep user's kernel-only/fixes-only,
no UART, cpus=1/USB-off, no further userspace inspection/edit and own-HID rule.

Latest hardware photos: IMG_3460.HEIC shows launchd exiting with OS_REASON_SIGNAL
2 / code 0xa (SIGBUS), plus userdata journal strategy ENXIO (6) during the
critical-exit sync. The driver's offline state is real, but the first underlying
SDHCI error is not visible; do not claim a proven SIGBUS origin or mask panic.
The same verified f72b97a image was booted again at the user's request, expected
phone/hfs-map-v2 checked, fastboot ACK in 0.467 s; private repeat receipt saved
under build/verified-f72b97a. IMG_3468.PNG then shows process sample 1/40 with
backboardd[56] and SpringBoard[26], each one thread. There is no panic or GUI in
this later photo. Do not claim SpringBoard works merely from those processes.

Next fixes: the BGRA default surface introduced by f72b97a was not scanned out
unless SwapEnd was submitted, unlike native physical default framebuffer memory.
Enable bounded 10 Hz direct refresh only after an eligible client successfully
gets its surface; leave untouched black storage/logs alone, display real colored
pixels, allow later black frames, stop direct refresh once layer swaps begin.
Panic/power gates remain. Empty SwapWait succeeds. Actual presenter and timer
ASan/UBSan tests exercise direct writes without any swap, RGB888 conversion,
refresh cadence, console takeover, black frames, layer takeover, panic/power and
buffer guards. Full host suite passed. Native Apple build/link still required.

IMG_3460 also provides complete touch status cmd60/reg02000018/value000004c0.
QUP MAX_OUTPUT_DONE was already set but the old test required OUT_FULL clear.
Honor counted DONE; input drains on SERVICE/DONE as upstream Linux v6.12 does.
Host actual transport tests cover the exact 0x4c0 completion and input service
without NOT_EMPTY, plus prior delayed-STOP/pending-output cases. No controller
firmware/PMIC power writes or simulated events. Physical touch still unverified.
No prepared userspace inspected/edited, no new diagnostics, UART, USB network,
SMP enable or flashing. Continue to the concrete checked image and hardware boot.
