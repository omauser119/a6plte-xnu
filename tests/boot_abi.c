/* SPDX-License-Identifier: BSD-2-Clause */
/* Compare the bridge ABI with this exact upstream kernel's native header. */
#include <stddef.h>
#include <pexpert/arm64/boot.h>
#include "../console/boot_abi.h"
_Static_assert(sizeof(boot_args) == sizeof(struct a6_boot_args), "BootArgs size");
_Static_assert(offsetof(boot_args, Video) == offsetof(struct a6_boot_args, video), "Video");
_Static_assert(offsetof(boot_args, deviceTreeP) == offsetof(struct a6_boot_args, device_tree), "DeviceTree");
_Static_assert(offsetof(boot_args, CommandLine) == offsetof(struct a6_boot_args, command_line), "CommandLine");
_Static_assert(offsetof(boot_args, bootFlags) == offsetof(struct a6_boot_args, boot_flags), "BootFlags");
_Static_assert(offsetof(boot_args, memSizeActual) == offsetof(struct a6_boot_args, mem_size_actual), "Memory size");
