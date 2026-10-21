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
