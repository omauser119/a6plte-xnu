ENTRY(_start)
SECTIONS {
 . = 0;
 .text : { KEEP(*(.text.boot)) *(.text*) }
 .rodata : { *(.rodata*) }
 .data : { *(.data*) }
 . = ALIGN(16); __bss_start = .;
 .bss (NOLOAD) : { *(.bss*) *(COMMON) . = ALIGN(16); }
 __bss_end = .;
 .stack (NOLOAD) : { . += 0x10000; } __stack_top = .;
 /* Include the zero-filled workspace in the Image so lk2nd doesn't place DTB there. */
 .pad : { BYTE(0); . = ALIGN(4096); }
 __image_end = .;
 /DISCARD/ : { *(.comment) *(.eh_frame*) *(.note*) }
}
