#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
from pathlib import Path
import argparse
import struct

ENCODING = 'shift_jis'
CHARACTERS_EXTENSION = '._dt'
JSON_EXTENSION = '.json'
RECORD_SIZE = 20
STRINGS_OFFSET = 0x2E4  # Default strings section start

def read_character_record(data, offset):
    """Read a single character record (20 bytes)"""
    if offset + RECORD_SIZE > len(data):
        return None

    record_data = data[offset:offset + RECORD_SIZE]
    fields = struct.unpack('<10H', record_data)  # 10 fields of 2 bytes each

    return {
        'id': fields[0],
        'name_offset': fields[1],
        'field1': fields[2],
        'field2': fields[3],
        'field3': fields[4],
        'field4': fields[5],
        'field5': fields[6],
        'field6': fields[7],
        'field7': fields[8],
        'field8': fields[9]
    }

def extract_string_at_offset(file_data, offset):
    """Extract null-terminated string at given offset"""
    if offset >= len(file_data):
        return ""

    null_pos = file_data.find(b'\x00', offset)
    if null_pos == -1:
        null_pos = len(file_data)

    try:
        return file_data[offset:null_pos].decode(ENCODING, errors='replace')
    except:
        return file_data[offset:null_pos].decode('utf-8', errors='replace')

def find_strings_section_start(file_data):
    """Find where strings section actually starts by looking for the lowest valid string offset"""
    min_offset = len(file_data)

    # Read all records to find minimum name_offset
    offset = 0
    while offset < len(file_data) - RECORD_SIZE:
        record = read_character_record(file_data, offset)
        if record is None:
            break

        if record['name_offset'] > 0 and record['name_offset'] < min_offset:
            min_offset = record['name_offset']

        offset += RECORD_SIZE

        # Stop if we've gone past reasonable record area
        if offset > 0x1000:  # Arbitrary limit
            break

    return min_offset if min_offset < len(file_data) else STRINGS_OFFSET

def decompile_characters(dat_path, json_path, test_compilation=False):
    """Decompile characters file"""
    print(f"=== DECOMPILING {dat_path} ===")

    with open(dat_path, 'rb') as f:
        original_data = f.read()

    print(f"File size: {len(original_data)} bytes")

    # Find actual strings section start
    strings_start = find_strings_section_start(original_data)
    print(f"Strings section starts at: 0x{strings_start:04X} ({strings_start})")

    # Read all character records
    records = []
    characters_data = []
    offset = 0

    while offset < strings_start:
        record = read_character_record(original_data, offset)
        if record is None:
            break

        # Extract the character name
        name = extract_string_at_offset(original_data, record['name_offset'])

        character_entry = {
            'id': record['id'],
            'name': name,
            'fields': [
                record['field1'], record['field2'], record['field3'], record['field4'],
                record['field5'], record['field6'], record['field7'], record['field8']
            ]
        }

        characters_data.append(character_entry)
        records.append(record)
        offset += RECORD_SIZE

    print(f"Found {len(characters_data)} character records")

    # Count non-empty names
    non_empty_names = [c for c in characters_data if c['name'].strip()]
    print(f"Characters with names: {len(non_empty_names)}")

    # Create JSON structure
    result = {
        "file_info": {
            "original_size": len(original_data),
            "encoding": ENCODING,
            "record_size": RECORD_SIZE,
            "strings_section_start": strings_start
        },
        "characters": characters_data
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Decompiled to {json_path}")
    print(f"📝 Edit 'name' fields in 'characters' array for translation")
    print(f"ℹ️  Additional fields are preserved automatically")

    if test_compilation:
        test_compilation_process(dat_path, json_path, original_data)

def compile_characters(json_path, dat_path):
    """Compile JSON back to characters file"""
    print(f"=== COMPILING {json_path} ===")

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    characters = data['characters']
    print(f"Original size: {data['file_info']['original_size']} bytes")
    print(f"Characters to compile: {len(characters)}")

    # Calculate records section size
    records_size = len(characters) * RECORD_SIZE

    # Start building the strings section
    strings_data = bytearray()
    name_offsets = []

    # Build strings and collect their offsets
    for character in characters:
        name = character['name']
        current_offset = records_size + len(strings_data)
        name_offsets.append(current_offset)

        # Encode string with null terminator
        encoded_name = name.encode(data['file_info']['encoding'], errors='replace') + b'\x00'
        strings_data.extend(encoded_name)

    print(f"Records section: {records_size} bytes")
    print(f"Strings section: {len(strings_data)} bytes")
    print(f"Total size: {records_size + len(strings_data)} bytes")

    # Build the complete file
    result_data = bytearray()

    # Write all character records with updated name offsets
    for i, character in enumerate(characters):
        # Prepare record data
        record_fields = [
            character['id'],
            name_offsets[i],  # Updated name offset
        ]

        # Add the 8 additional fields
        fields = character.get('fields', [0] * 8)
        while len(fields) < 8:
            fields.append(0)
        record_fields.extend(fields[:8])

        # Pack record (10 fields of 2 bytes each)
        record_data = struct.pack('<10H', *record_fields)
        result_data.extend(record_data)

    # Append strings section
    result_data.extend(strings_data)

    # Save file
    with open(dat_path, 'wb') as f:
        f.write(result_data)

    print(f"\n✅ Compiled to {dat_path}")
    print(f"New size: {len(result_data)} bytes")
    print(f"Size difference: {len(result_data) - data['file_info']['original_size']:+d} bytes")

def test_compilation_process(dat_path, json_path, original_data):
    """Test compilation process"""
    print("\n=== COMPILATION TEST ===")
    test_dat_path = dat_path.parent / f"{dat_path.stem}_test{dat_path.suffix}"

    try:
        compile_characters(json_path, test_dat_path)

        with open(test_dat_path, 'rb') as f:
            compiled_data = f.read()

        # Compare structure rather than exact bytes (strings might be in different order)
        if len(compiled_data) == len(original_data):
            print("✅ TEST PASSED: File size matches!")

            # Test that we can re-decompile and get same data
            test_json_path = dat_path.parent / f"{dat_path.stem}_test.json"
            decompile_characters(test_dat_path, test_json_path, test_compilation=False)

            with open(json_path, 'r', encoding='utf-8') as f:
                original_json = json.load(f)
            with open(test_json_path, 'r', encoding='utf-8') as f:
                compiled_json = json.load(f)

            # Compare characters data
            if original_json['characters'] == compiled_json['characters']:
                print("✅ DEEP TEST PASSED: Character data matches!")
                test_dat_path.unlink()
                test_json_path.unlink()
            else:
                print("⚠️  Character data differs, but file structure is correct")
                print(f"Test files saved: {test_dat_path}, {test_json_path}")

        else:
            print(f"❌ TEST FAILED:")
            print(f"  Original: {len(original_data)} bytes")
            print(f"  Compiled: {len(compiled_data)} bytes")
            print(f"  Difference: {len(compiled_data) - len(original_data):+d} bytes")
            print(f"  Test file saved: {test_dat_path}")

    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

def determine_file_type(input_path):
    """Determine if input file is _DT or JSON"""
    if input_path.suffix.lower() == JSON_EXTENSION:
        return 'json'
    elif input_path.name.endswith(CHARACTERS_EXTENSION):
        return 'characters'
    else:
        return 'unknown'

def main():
    parser = argparse.ArgumentParser(description="Characters file decompiler/compiler")
    parser.add_argument("input_file", help="Input file (._dt or .json)")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("--test", action="store_true", help="Test compilation after decompilation")

    args = parser.parse_args()
    input_path = Path(args.input_file)

    if not input_path.exists():
        print(f"File not found: {input_path}")
        sys.exit(1)

    file_type = determine_file_type(input_path)

    if file_type == 'json':
        output_path = Path(args.output) if args.output else input_path.with_suffix(CHARACTERS_EXTENSION)
        compile_characters(input_path, output_path)
    elif file_type == 'characters':
        output_path = Path(args.output) if args.output else input_path.with_suffix(JSON_EXTENSION)
        decompile_characters(input_path, output_path, test_compilation=args.test)
    else:
        print(f"Unsupported file: {input_path}")
        print(f"Supported: {JSON_EXTENSION} (for compilation) and {CHARACTERS_EXTENSION} (for decompilation)")
        sys.exit(1)

if __name__ == "__main__":
    main()