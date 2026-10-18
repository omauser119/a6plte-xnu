/* SPDX-License-Identifier: BSD-2-Clause */
#ifndef A6_BOOT_ABI_H
#define A6_BOOT_ABI_H
#include <stdint.h>
#include <stddef.h>
/* Exact LP64 layout of rel/xnu-12377 pexpert/pexpert/arm64/boot.h. */
struct a6_boot_video { uint64_t base, display, stride, width, height, depth; };
struct a6_boot_args {
    uint16_t revision, version;
    uint32_t pad0;
    uint64_t virt_base, phys_base, mem_size, top_of_kernel_data;
    struct a6_boot_video video;
    uint32_t machine_type, pad1;
    uint64_t device_tree;
    uint32_t device_tree_length;
    char command_line[1024];
    uint32_t pad2;
    uint64_t boot_flags, mem_size_actual;
};
_Static_assert(offsetof(struct a6_boot_args,video)==40,"Video ABI");
_Static_assert(offsetof(struct a6_boot_args,device_tree)==96,"DeviceTree ABI");
_Static_assert(offsetof(struct a6_boot_args,command_line)==108,"CommandLine ABI");
_Static_assert(offsetof(struct a6_boot_args,boot_flags)==1136,"BootFlags ABI");
_Static_assert(sizeof(struct a6_boot_args)==1152,"boot_args ABI");
#endif
