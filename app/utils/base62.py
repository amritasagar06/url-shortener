# app/utils/base62.py
import secrets

ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
BASE = len(ALPHABET)

def encode(num: int) -> str:
    """Encodes a positive integer into a Base-62 string."""
    if num == 0:
        return ALPHABET[0]
    
    arr = []
    while num:
        num, rem = divmod(num, BASE)
        arr.append(ALPHABET[rem])
    arr.reverse()
    return "".join(arr)

def generate_random_secure_id() -> int:
    """Generates a cryptographically secure large integer for encoding."""
    # Generates an integer within a range that yields an elegant 6-to-8 character short code
    return secrets.randbelow(56_800_235_584) + 916_132_832