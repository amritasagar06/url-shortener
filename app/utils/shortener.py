import string
import random

# Base-62 character set: 26 lowercase + 26 uppercase + 10 digits
BASE62_ALPHABET = string.ascii_letters + string.digits  

def generate_short_code(length: int = 6) -> str:
    """
    Day 3/5 Component: Generates a secure, random string of base62 characters.
    
    A length of 6 characters gives 62^6 = 56.8 Billion unique combinations,
    which keeps our shortened URLs incredibly compact while minimizing the 
    risk of hash collisions.
    """
    return "".join(random.choices(BASE62_ALPHABET, k=length))