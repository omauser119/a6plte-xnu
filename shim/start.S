/* SPDX-License-Identifier: BSD-2-Clause */
.section .text.boot,"ax"
.global _start
_start:
    b entry
    .long 0
    .quad 0x80000
    .quad __image_end - _start
    .quad 0
    .quad 0
    .quad 0
    .quad 0
    .ascii "ARM\x64"
    .long 0
entry:
    msr daifset, #15
    mov x19, x0
    adrp x1, __stack_top
    add x1, x1, :lo12:__stack_top
    mov sp, x1
    adrp x1, __bss_start
    add x1, x1, :lo12:__bss_start
    adrp x2, __bss_end
    add x2, x2, :lo12:__bss_end
1:  cmp x1, x2
    b.hs 2f
    str xzr, [x1], #8
    b 1b
2:  mov x0, x19
    bl shim_main
3:  wfe
    b 3b
