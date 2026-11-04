/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
/* Original test doubles for the pinned loader API. Host addresses intentionally
 * use uintptr_t: this tests shell control flow, not Xtensa ELF execution. */
enum {ELF_SEC_TEXT, ELF_SEC_BSS, ELF_SEC_DATA, ELF_SEC_RODATA, ELF_SEC_DRLRO,
      ELF_SEC_GOT_LOC, ELF_SEC_PREINIT, ELF_SEC_INIT, ELF_SEC_FINI, ELF_SECS};
enum {SHT_SYMTAB=2, SHT_STRTAB=3, SHT_SYNSYM=11, SHN_UNDEF=0};
typedef struct {uint8_t ident[16]; uint16_t type,machine; uint32_t version,entry,phoff,shoff,flags;
    uint16_t ehsize,phentsize,phnum,shentsize,shnum,shstrndx;} elf32_hdr_t;
typedef struct {uint32_t name,type,flags,addr,offset,size,link,info,addralign,entsize;} elf32_shdr_t;
typedef struct {uint32_t name,value,size; uint8_t info,other; uint16_t shndx;} elf32_sym_t;
typedef struct {uintptr_t addr; uint32_t size;} esp_elf_sec_t;
typedef struct {
    esp_elf_sec_t sec[ELF_SECS];
    int (*entry)(int, char **);
    void *ptext;
    bool init_done;
    void (**preinit_array)(void), (**init_array)(void), (**fini_array)(void);
    uint32_t preinit_count,init_count,fini_count;
} esp_elf_t;
int esp_elf_init(esp_elf_t *);
int esp_elf_relocate(esp_elf_t *,const uint8_t *,size_t);
int esp_elf_request(esp_elf_t *,int,int,char **);
void esp_elf_deinit(esp_elf_t *);
uintptr_t esp_elf_runtime_base(esp_elf_t *);
