#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
t_fish._dt - Декомпилятор/Компилятор (Trails to Azure)
Финальная версия - объединяет лучшее из обоих скриптов
"""

import struct
import json
from pathlib import Path

GAME_ENCODING = 'shift_jis'


class FishFileDecompiler:
    def __init__(self, filepath):
        self.filepath = Path(filepath)
        with open(filepath, 'rb') as f:
            self.data = f.read()

        header = struct.unpack_from('<HHHHHHHH', self.data, 0)
        self.header_size = header[0]
        self.unknown1 = header[1]
        self.unknown2 = header[2]
        self.npc_names_offset = header[3]
        self.service_data_offset = header[4]
        self.quest_data_offset = header[5]
        self.unknown3 = header[6]
        self.notebook_offset = header[7]

        print(f'[Заголовок]')
        print(f'  header_size: 0x{self.header_size:04X}')
        print(f'  notebook_offset: 0x{self.notebook_offset:04X}')
        print(f'  npc_names_offset: 0x{self.npc_names_offset:04X}')
        print(f'  service_data_offset: 0x{self.service_data_offset:04X}')
        print(f'  quest_data_offset: 0x{self.quest_data_offset:04X}')

    def extract_metadata(self):
        """48 записей по 58 байт - как HEX строки"""
        metadata_start = 0x10
        metadata_end = self.notebook_offset
        entry_size = 58
        num_entries = (metadata_end - metadata_start) // entry_size

        metadata = []
        for i in range(num_entries):
            offset = metadata_start + i * entry_size
            entry_bytes = self.data[offset:offset + entry_size]
            metadata.append(entry_bytes.hex())

        print(f'\n[Метаданные]')
        print(f'  Записей: {num_entries}')
        return metadata

    def extract_notebook_texts(self):
        """31 описание рыб"""
        start = self.notebook_offset
        end = self.npc_names_offset

        notebook_data = self.data[start:end]
        texts = []
        for text_bytes in notebook_data.split(b'\x00'):
            if text_bytes:
                texts.append(text_bytes.decode(GAME_ENCODING, errors='replace'))

        print(f'\n[Блокнот]')
        print(f'  Текстов: {len(texts)}')
        return texts

    def extract_npc_names(self):
        """5 имён NPC"""
        start = self.npc_names_offset
        end = self.service_data_offset

        # Первые 10 байт - указатели (сохраняем их в raw_data)
        npc_section = self.data[start:end]

        # Имена начинаются после указателей
        names_data = npc_section[10:]
        names = []
        for name_bytes in names_data.split(b'\x00'):
            if name_bytes:
                names.append(name_bytes.decode(GAME_ENCODING, errors='replace'))

        print(f'\n[Имена NPC]')
        print(f'  Имён: {len(names)}')
        for i, name in enumerate(names):
            print(f'    [{i}] {name}')

        return names

    def extract_service_data(self):
        """Служебные данные как HEX"""
        start = self.service_data_offset
        end = self.quest_data_offset

        service_bytes = self.data[start:end]

        print(f'\n[Служебные данные]')
        print(f'  Размер: {len(service_bytes)} байт')

        return service_bytes.hex()

    def extract_quest_texts(self):
        """120 указателей + тексты БЕЗ PADDING"""
        pointers_start = self.quest_data_offset
        pointers_count = 120
        pointers_end = pointers_start + pointers_count * 2

        pointers = struct.unpack_from(f'<{pointers_count}H', self.data, pointers_start)

        # Тексты СРАЗУ после указателей (БЕЗ padding байта!)
        text_start = pointers_end
        quest_data = self.data[text_start:]

        texts = []
        for text_bytes in quest_data.split(b'\x00'):
            texts.append(text_bytes.decode(GAME_ENCODING, errors='replace'))

        if texts and not texts[-1]:
            texts = texts[:-1]

        print(f'\n[Quest тексты]')
        print(f'  Указателей: {pointers_count}')
        print(f'  Текстов: {len(texts)}')
        print(f'  Первый указатель: 0x{pointers[0]:04X}')
        print(f'  Начало текстов: 0x{text_start:04X}')

        return list(pointers), texts

    def decompile(self, output_path=None):
        if output_path is None:
            output_path = self.filepath.with_suffix('.json')

        print(f'\n{"="*60}')
        print(f'Декомпиляция: {self.filepath}')
        print(f'{"="*60}')

        metadata = self.extract_metadata()
        notebook_texts = self.extract_notebook_texts()
        npc_names = self.extract_npc_names()
        service_data = self.extract_service_data()
        quest_pointers, quest_texts = self.extract_quest_texts()

        result = {
            'header': {
                'header_size': self.header_size,
                'unknown1': self.unknown1,
                'unknown2': self.unknown2,
                'npc_names_offset': self.npc_names_offset,
                'service_data_offset': self.service_data_offset,
                'quest_data_offset': self.quest_data_offset,
                'unknown3': self.unknown3,
                'notebook_offset': self.notebook_offset
            },
            'metadata': metadata,
            'notebook_texts': notebook_texts,
            'npc_names': npc_names,
            'service_data': service_data,
            'quest_texts': {
                'pointers': quest_pointers,
                'texts': quest_texts
            }
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f'\n✅ Результат: {output_path}')

        # Автотест
        self.test_compilation(output_path)
        return result

    def test_compilation(self, json_path):
        """Автотест"""
        print(f'\n{"="*60}')
        print(f'АВТОТЕСТ КОМПИЛЯЦИИ')
        print(f'{"="*60}')

        test_output = self.filepath.parent / f"{self.filepath.stem}_test{self.filepath.suffix}"

        try:
            compiler = FishFileCompiler(json_path)
            compiler.compile(test_output)

            with open(self.filepath, 'rb') as f:
                original = f.read()
            with open(test_output, 'rb') as f:
                compiled = f.read()

            print(f'\n[Сравнение]')
            print(f'  Оригинал: {len(original)} байт')
            print(f'  Собрано:  {len(compiled)} байт')

            if original == compiled:
                print(f'\n✅ ТЕСТ ПРОЙДЕН!')
                test_output.unlink()
                return True
            else:
                print(f'\n❌ ТЕСТ НЕ ПРОЙДЕН')

                for i in range(min(len(original), len(compiled))):
                    if original[i] != compiled[i]:
                        print(f'\n[Первое отличие: 0x{i:04X}]')
                        print(f'  Orig: 0x{original[i]:02X}')
                        print(f'  Comp: 0x{compiled[i]:02X}')
                        break

                print(f'\n💾 Тестовый файл: {test_output}')
                return False

        except Exception as e:
            print(f'\n❌ ОШИБКА: {e}')
            import traceback
            traceback.print_exc()
            return False


class FishFileCompiler:
    def __init__(self, json_path):
        self.json_path = Path(json_path)
        with open(json_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

    def compile(self, output_path=None):
        if output_path is None:
            output_path = self.json_path.with_suffix('._dt')

        print(f'\n{"="*60}')
        print(f'Компиляция: {self.json_path}')
        print(f'{"="*60}')

        binary_data = bytearray(16)

        # ========== МЕТАДАННЫЕ ==========
        print(f'\n[Метаданные]')

        # Вычисляем будущие АБСОЛЮТНЫЕ оффсеты текстов блокнота
        text_absolute_offsets = []
        current_offset = 0x10 + len(self.data['metadata']) * 58

        for text in self.data['notebook_texts']:
            text_absolute_offsets.append(current_offset)
            current_offset += len(text.encode(GAME_ENCODING)) + 1

        print(f'  Записей: {len(self.data["metadata"])}')
        print(f'  Текстов в блокноте: {len(text_absolute_offsets)}')

        # Паттерн из старого скрипта:
        # Записи 1-29, байты [(N-1)*2] → Тексты 1-29
        # Запись 31, байты [0] → Текст 30
        for entry_idx, meta_hex in enumerate(self.data['metadata']):
            meta_bytes = bytearray.fromhex(meta_hex)

            if 1 <= entry_idx <= 29:
                text_idx = entry_idx
                byte_pos = (entry_idx - 1) * 2
                if text_idx < len(text_absolute_offsets):
                    new_abs_offset = text_absolute_offsets[text_idx]
                    struct.pack_into('<H', meta_bytes, byte_pos, new_abs_offset)

            elif entry_idx == 31:
                text_idx = 30
                byte_pos = 0
                if text_idx < len(text_absolute_offsets):
                    new_abs_offset = text_absolute_offsets[text_idx]
                    struct.pack_into('<H', meta_bytes, byte_pos, new_abs_offset)

            binary_data.extend(meta_bytes)

        print(f'  Обновлено АБСОЛЮТНЫХ указателей: 30')

        # ========== БЛОКНОТ ==========
        notebook_offset = len(binary_data)
        print(f'\n[Блокнот] 0x{notebook_offset:04X}')

        for text in self.data['notebook_texts']:
            binary_data.extend(text.encode(GAME_ENCODING))
            binary_data.append(0x00)

        # ========== NPC ИМЕНА ==========
        npc_names_offset = len(binary_data)
        print(f'\n[NPC имена] 0x{npc_names_offset:04X}')

        # Вычисляем позиции имён
        npc_positions = []
        pos = npc_names_offset + 10

        for name in self.data['npc_names']:
            npc_positions.append(pos)
            pos += len(name.encode(GAME_ENCODING)) + 1

        # Резервируем 10 байт для указателей
        binary_data.extend(b'\x00' * 10)

        # Записываем указатели
        for i, npc_pos in enumerate(npc_positions):
            struct.pack_into('<H', binary_data, npc_names_offset + i * 2, npc_pos)

        # Записываем имена
        for name in self.data['npc_names']:
            binary_data.extend(name.encode(GAME_ENCODING))
            binary_data.append(0x00)

        # ========== SERVICE DATA ==========
        service_data_offset = len(binary_data)
        print(f'\n[Service data] 0x{service_data_offset:04X}')

        service_bytes = bytearray.fromhex(self.data['service_data'])

        # Пересчёт указателей (они указывают внутрь секции)
        for i in range(5):
            new_ptr = service_data_offset + 10 + (i * 48)
            struct.pack_into('<H', service_bytes, i * 2, new_ptr)

        binary_data.extend(service_bytes)

        # ========== QUEST DATA ==========
        quest_data_offset = len(binary_data)
        print(f'\n[Quest data] 0x{quest_data_offset:04X}')

        quest_texts = self.data['quest_texts']['texts']
        orig_pointers = self.data['quest_texts']['pointers']

        # Резервируем 240 байт для указателей
        pointers_start = len(binary_data)
        binary_data.extend(b'\x00' * 240)

        # ВАЖНО: Тексты СРАЗУ после указателей (БЕЗ padding!)
        text_start = len(binary_data)
        text_positions = []

        for text in quest_texts:
            text_positions.append(len(binary_data))
            binary_data.extend(text.encode(GAME_ENCODING))
            binary_data.append(0x00)

        # Маппинг из старого скрипта (работает!)
        unique_orig_ptrs = sorted(set(orig_pointers))

        # Если уникальных указателей больше чем текстов,
        # последний указывает за конец
        if len(unique_orig_ptrs) > len(quest_texts):
            unique_orig_ptrs = unique_orig_ptrs[:-1]

        orig_ptr_to_text_idx = {}
        for i, orig_ptr in enumerate(unique_orig_ptrs):
            if i < len(quest_texts):
                orig_ptr_to_text_idx[orig_ptr] = i

        # Обновляем все 120 указателей
        for idx, orig_ptr in enumerate(orig_pointers):
            if orig_ptr in orig_ptr_to_text_idx:
                text_idx = orig_ptr_to_text_idx[orig_ptr]
                new_ptr = text_positions[text_idx]
            else:
                # За пределы данных
                new_ptr = len(binary_data)

            struct.pack_into('<H', binary_data, pointers_start + idx * 2, new_ptr)

        print(f'  Первый указатель → 0x{text_start:04X}')
        print(f'  Уникальных указателей: {len(orig_ptr_to_text_idx)}')

        # ========== ЗАГОЛОВОК ==========
        header = self.data['header']
        struct.pack_into('<H', binary_data, 0x00, header['header_size'])
        struct.pack_into('<H', binary_data, 0x02, header['unknown1'])
        struct.pack_into('<H', binary_data, 0x04, header['unknown2'])
        struct.pack_into('<H', binary_data, 0x06, npc_names_offset)
        struct.pack_into('<H', binary_data, 0x08, service_data_offset)
        struct.pack_into('<H', binary_data, 0x0A, quest_data_offset)
        struct.pack_into('<H', binary_data, 0x0C, header['unknown3'])
        struct.pack_into('<H', binary_data, 0x0E, notebook_offset)

        with open(output_path, 'wb') as f:
            f.write(binary_data)

        print(f'\n✅ Сохранено: {output_path} ({len(binary_data)} байт)')
        return output_path


def main():
    import sys

    if len(sys.argv) < 2:
        print('Fish Tool - t_fish._dt')
        print('Использование: python fish_tool_FINAL.py <файл>')
        input('\nEnter для выхода...')
        sys.exit(1)

    input_file = Path(sys.argv[1])

    if not input_file.exists():
        print(f'❌ Файл не найден')
        input('\nEnter для выхода...')
        sys.exit(1)

    try:
        if input_file.suffix == '.json':
            FishFileCompiler(input_file).compile()
        elif input_file.suffix in ['._dt', '.dt']:
            FishFileDecompiler(input_file).decompile()
        else:
            print(f'❌ Неподдерживаемый формат')
            input('\nEnter для выхода...')
            sys.exit(1)

    except Exception as e:
        print(f'\n❌ ОШИБКА: {e}')
        import traceback
        traceback.print_exc()
        input('\nEnter для выхода...')
        sys.exit(1)

    input('\nEnter для выхода...')


if __name__ == '__main__':
    main()