"""
Regression test for unknown-8bit encoding issue
Tests that emails with non-standard charsets like 'unknown-8bit' are handled gracefully.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.legacy_operations import decode_mime_words
import email


def test_unknown_8bit_encoding():
    """Test handling of 'unknown-8bit' charset in MIME headers"""
    # Simulate a header with unknown-8bit encoding
    test_cases = [
        ("=?unknown-8bit?Q?Test_Subject?=", "Test Subject"),
        ("=?unknown-8bit?B?VGVzdCBTdWJqZWN0?=", "Test Subject"),
        ("=?x-unknown?Q?Another_Test?=", "Another Test"),
        ("=?8bit?Q?Simple?=", "Simple"),
        ("=?unknown?Q?Fallback?=", "Fallback"),
    ]
    
    for encoded_header, expected_text in test_cases:
        result = decode_mime_words(encoded_header)
        assert expected_text in result, f"Failed to decode '{encoded_header}', got '{result}'"
        print(f"✓ Decoded '{encoded_header}' -> '{result}'")


def test_mixed_valid_and_unknown_encoding():
    """Test headers with both valid and unknown encodings"""
    # Mix of UTF-8 and unknown-8bit
    test_header = "=?utf-8?Q?Valid_Part?= =?unknown-8bit?Q?_Unknown_Part?="
    result = decode_mime_words(test_header)
    
    assert "Valid Part" in result
    assert "Unknown Part" in result
    print(f"✓ Mixed encoding decoded: '{result}'")


def test_unknown_encoding_with_special_chars():
    """Test unknown encoding with special characters that might fail"""
    # Test headers with special characters in unknown-8bit encoding
    test_cases = [
        "=?unknown-8bit?Q?Caf=E9?=",  # café in latin-1
        "=?unknown-8bit?B?VMOpcw==?=",  # Test in base64
        "=?x-unknown?Q?R=E9sum=E9?=",  # Résumé
    ]
    
    for header in test_cases:
        result = decode_mime_words(header)
        assert len(result) > 0, f"Failed to decode '{header}'"
    
    print(f"✓ Special chars decoded successfully")


def test_completely_invalid_charset():
    """Test a charset that doesn't exist at all"""
    # Test with a completely made-up charset
    # decode_mime_words should handle it gracefully with fallback
    test_header = "=?nonexistent-charset-xyz?Q?Test_content?="
    
    result = decode_mime_words(test_header)
    # Should not crash, should return something
    assert result is not None
    assert len(result) > 0
    print(f"✓ Invalid charset handled: '{result}'")


def test_empty_and_none_values():
    """Test edge cases with empty or None values"""
    assert decode_mime_words("") == ""
    assert decode_mime_words(None) == ""
    
    # Plain ASCII (no encoding)
    plain = "Plain ASCII text"
    assert decode_mime_words(plain) == plain
    
    print("✓ Empty and plain values handled correctly")


def test_real_world_unknown_8bit_email():
    """Test a realistic email with unknown-8bit encoding"""
    # Create a minimal email with unknown-8bit in Content-Type
    raw_email = b"""From: sender@example.com
To: recipient@example.com
Subject: =?unknown-8bit?Q?Test_Subject?=
Content-Type: text/plain; charset="unknown-8bit"

Test body content
"""
    
    # Parse the email
    msg = email.message_from_bytes(raw_email)
    
    # Decode the subject using our function
    subject = decode_mime_words(msg.get('Subject', ''))
    
    assert "Test Subject" in subject
    print(f"✓ Real-world email parsed successfully, subject: '{subject}'")


if __name__ == '__main__':
    print("=" * 60)
    print("Testing unknown-8bit encoding handling")
    print("=" * 60)
    
    test_unknown_8bit_encoding()
    test_mixed_valid_and_unknown_encoding()
    test_unknown_encoding_with_special_chars()
    test_completely_invalid_charset()
    test_empty_and_none_values()
    test_real_world_unknown_8bit_email()
    
    print("=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)

