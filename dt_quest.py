#!/usr/bin/env python3
"""
Trails from Zero Quest DT Decompiler
Converts ._dt files to JSON format for easier translation work
Based on the Ivdos structure from the HTML viewer/editor
"""

import struct
import json
import sys
import argparse
from pathlib import Path


class QuestDTDecompiler:
    ENTRY_COUNT = 80
    ENTRY_SIZE = 28  # 1(counter) + 11(reserved) + 4 + 4 + 4 + 4
    ENCODING = 'shift_jis'
    
    def __init__(self):
        self.entries = []
        self.file_size = 0
    
    def read_cstring_sjis(self, data, ptr):
        """Read null-terminated SJIS string at given pointer"""
        if not ptr or ptr < 0 or ptr >= len(data):
            return ""
        
        # Find null terminator
        end = ptr
        while end < len(data) and data[end] != 0:
            end += 1
        
        # Decode SJIS string
        try:
            text = data[ptr:end].decode(self.ENCODING, errors='replace')
            return text.replace('\u0001', '<LINE>')
        except Exception as e:
            print(f"Warning: SJIS decode error at 0x{ptr:X}: {e}")
            return ""

    def parse_dt_file(self, file_path):
        """Parse ._dt file according to the structure"""
        with open(file_path, 'rb') as f:
            data = f.read()

        self.file_size = len(data)

        if len(data) < self.ENTRY_COUNT * self.ENTRY_SIZE:
            raise ValueError(f"File too small for header table. Need at least {self.ENTRY_COUNT * self.ENTRY_SIZE} bytes")

        # Step 1: Read header entries
        headers = []
        for idx in range(self.ENTRY_COUNT):
            offset = idx * self.ENTRY_SIZE

            # Read header structure
            counter = data[offset]
            reserved = data[offset + 1:offset + 12]  # 11 bytes
            name_ptr = struct.unpack('<I', data[offset + 12:offset + 16])[0]
            client_ptr = struct.unpack('<I', data[offset + 16:offset + 20])[0]
            description_ptr = struct.unpack('<I', data[offset + 20:offset + 24])[0]
            progress_ptr = struct.unpack('<I', data[offset + 24:offset + 28])[0]

            headers.append({
                'idx': idx,
                'counter': counter,
                'reserved': list(reserved),
                'name_ptr': name_ptr,
                'client_ptr': client_ptr,
                'description_ptr': description_ptr,
                'progress_ptr': progress_ptr
            })

        # Step 2: Decode strings and create entries
        entries = []
        for h in headers:
            entry = {
                'index': h['idx'],
                'counter': h['counter'],
                'reserved': h['reserved'],
                'reserved_hex': ' '.join(f'{b:02x}' for b in h['reserved']),
                'name': self.read_cstring_sjis(data, h['name_ptr']),
                'client': self.read_cstring_sjis(data, h['client_ptr']),
                'description': self.read_cstring_sjis(data, h['description_ptr']),
                'progress': [],
                'pointers': {
                    'name_ptr': f"0x{h['name_ptr']:08X}",
                    'client_ptr': f"0x{h['client_ptr']:08X}",
                    'description_ptr': f"0x{h['description_ptr']:08X}",
                    'progress_ptr': f"0x{h['progress_ptr']:08X}"
                }
            }
            entries.append(entry)

        # Step 3: Read progress arrays
        for i in range(self.ENTRY_COUNT):
            this_ptr = headers[i]['progress_ptr']
            if not this_ptr:
                entries[i]['progress'] = []
                continue

            # Calculate size of progress array
            size_bytes = 0
            if i < self.ENTRY_COUNT - 1:
                next_ptr = headers[i + 1]['progress_ptr']
                if next_ptr > this_ptr and next_ptr <= len(data):
                    size_bytes = next_ptr - this_ptr
                else:
                    # Fallback: read until EOF
                    size_bytes = len(data) - this_ptr if this_ptr < len(data) else 0
            else:
                # Last entry: read until EOF
                size_bytes = len(data) - this_ptr if this_ptr < len(data) else 0

            # Read progress entries (each is a 4-byte pointer to string)
            count = max(0, size_bytes // 4)
            progress_list = []

            for j in range(count):
                try:
                    ptr_offset = this_ptr + j * 4
                    if ptr_offset + 4 <= len(data):
                        text_ptr = struct.unpack('<I', data[ptr_offset:ptr_offset + 4])[0]
                        text = self.read_cstring_sjis(data, text_ptr)
                        progress_list.append(text)
                    else:
                        break
                except Exception as e:
                    print(f"Warning: Error reading progress entry {j} for quest {i}: {e}")
                    break

            entries[i]['progress'] = progress_list

        self.entries = entries
        return entries

    def to_json(self, output_path=None, indent=2):
        """Export parsed data to JSON"""
        output = {
            'metadata': {
                'format': 'Trails from Zero Quest DT',
                'encoding': self.ENCODING,
                'endianness': 'little',
                'entry_count': self.ENTRY_COUNT,
                'entry_size': self.ENTRY_SIZE,
                'file_size': self.file_size
            },
            'quests': self.entries
        }

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=indent)
            print(f"JSON exported to: {output_path}")
        else:
            return json.dumps(output, ensure_ascii=False, indent=indent)

    def from_json(self, json_path):
        """Load data from JSON for recompilation"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.entries = data['quests']
        return self.entries

    def encode_sjis_with_null(self, text):
        """Encode string to SJIS with null terminator"""
        if not text:
            return b'\x00'
        try:
            text = text.replace('<LINE>', '\u0001')
            encoded = text.encode(self.ENCODING, errors='replace')
            return encoded + b'\x00'
        except Exception as e:
            print(f"Warning: SJIS encode error for '{text}': {e}")
            return b'\x00'

    def compile_to_dt(self, output_path):
        """Compile JSON data back to ._dt format"""
        if not self.entries:
            raise ValueError("No entries loaded. Load JSON data first.")

        # Calculate header size
        header_size = self.ENTRY_COUNT * self.ENTRY_SIZE
        header = bytearray(header_size)

        # Body parts and cursor for allocation
        body_parts = []
        cursor = header_size

        def allocate(data):
            nonlocal cursor
            start = cursor
            body_parts.append(data)
            cursor += len(data)
            return start

        # Allocate strings first
        for entry in self.entries:
            entry['_name_ptr'] = allocate(self.encode_sjis_with_null(entry.get('name', '')))
            entry['_client_ptr'] = allocate(self.encode_sjis_with_null(entry.get('client', '')))
            entry['_desc_ptr'] = allocate(self.encode_sjis_with_null(entry.get('description', '')))

        # Allocate progress strings and arrays
        for entry in self.entries:
            progress = entry.get('progress', [])
            if not progress:
                entry['_progress_ptr'] = 0
                continue

            # Allocate progress text strings
            progress_ptrs = []
            for text in progress:
                ptr = allocate(self.encode_sjis_with_null(text))
                progress_ptrs.append(ptr)

            # Allocate progress pointer array
            progress_array = b''.join(struct.pack('<I', ptr) for ptr in progress_ptrs)
            entry['_progress_ptr'] = allocate(progress_array)

        # Write header
        for entry in self.entries:
            offset = entry['index'] * self.ENTRY_SIZE

            # Counter (1 byte)
            header[offset] = entry.get('counter', 0) & 0xFF

            # Reserved (11 bytes)
            reserved = entry.get('reserved', [0] * 11)
            for i in range(11):
                header[offset + 1 + i] = reserved[i] if i < len(reserved) else 0

            # Pointers (4 bytes each, little endian)
            struct.pack_into('<I', header, offset + 12, entry['_name_ptr'])
            struct.pack_into('<I', header, offset + 16, entry['_client_ptr'])
            struct.pack_into('<I', header, offset + 20, entry['_desc_ptr'])
            struct.pack_into('<I', header, offset + 24, entry['_progress_ptr'])

        # Combine header and body
        body = b''.join(body_parts)
        final_data = bytes(header) + body

        # Write to file
        with open(output_path, 'wb') as f:
            f.write(final_data)

        print(f"Compiled DT file saved to: {output_path}")
        print(f"File size: {len(final_data)} bytes")


def main():
    parser = argparse.ArgumentParser(description='Trails from Zero Quest DT Decompiler/Compiler')
    parser.add_argument('input', help='Input file path')
    parser.add_argument('-o', '--output', help='Output file path')
    parser.add_argument('-c', '--compile', action='store_true',
                       help='Compile JSON back to DT format (default: decompile DT to JSON)')
    parser.add_argument('--indent', type=int, default=2,
                       help='JSON indentation (default: 2)')

    args = parser.parse_args()

    decompiler = QuestDTDecompiler()
    input_path = Path(args.input)

    # Auto-detect mode based on file extension
    is_json = input_path.suffix.lower() == '.json'
    if is_json and not args.compile:
        args.compile = True  # Auto-compile JSON to DT

    try:
        if args.compile:
            # Compile JSON to DT
            output_path = args.output
            if not output_path:
                output_path = input_path.with_suffix('._dt')

            print(f"Compiling JSON to DT: {input_path} -> {output_path}")
            decompiler.from_json(input_path)
            decompiler.compile_to_dt(output_path)

        else:
            # Decompile DT to JSON
            output_path = args.output
            if not output_path:
                output_path = input_path.with_suffix('.json')

            print(f"Decompiling DT to JSON: {input_path} -> {output_path}")
            decompiler.parse_dt_file(input_path)
            decompiler.to_json(output_path, indent=args.indent)

            # Print summary
            print(f"\nSummary:")
            print(f"- Total quests: {len(decompiler.entries)}")
            print(f"- File size: {decompiler.file_size} bytes")

            non_empty = sum(1 for e in decompiler.entries if e['name'] or e['client'] or e['description'])
            print(f"- Non-empty entries: {non_empty}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()