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

/* The bridge runs at EL1 with translation off. Keep faults on the display
 * instead of taking an exception through a stale firmware VBAR_EL1. */
.global shim_install_vectors
shim_install_vectors:
    adr x0, shim_vectors
    msr vbar_el1, x0
    isb
    ret

.balign 2048
shim_vectors:
.set vector_slot, 0
.rept 16
    mov x0, #vector_slot
    b shim_fault
    .balign 128
    .set vector_slot, vector_slot + 1
.endr
shim_fault:
    msr daifset, #15
    mrs x1, esr_el1
    mrs x2, elr_el1
    mrs x3, far_el1
    mrs x4, sctlr_el1
    adrp x5, __stack_top
    add x5, x5, :lo12:__stack_top
    mov sp, x5
    bl shim_fault_report
4:  wfe
    b 4b
