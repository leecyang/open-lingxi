import time
import jwt
from typing import Optional


def generate_jwt_from_apikey(apikey: str, exp_seconds: int = 3600) -> str:
    """
    Generate JWT token from API key according to Jiutian API specification.
    
    Args:
        apikey: API key in format "id.secret"
        exp_seconds: Token expiration time in seconds (default: 3600 = 1 hour)
    
    Returns:
        JWT token string
    
    Raises:
        Exception: If apikey format is invalid
    """
    try:
        # Split API key into id and secret
        parts = apikey.split(".", 1)
        if len(parts) != 2:
            raise Exception("invalid apikey format, expected 'id.secret'")
        
        api_key_id, secret = parts
        
        # Create payload according to Jiutian specification
        current_time = int(round(time.time()))
        payload = {
            "api_key": api_key_id,
            "exp": current_time + exp_seconds,
            "timestamp": current_time,
        }
        
        # Generate JWT token with HS256 algorithm
        token = jwt.encode(
            payload,
            secret,
            algorithm="HS256",
            headers={
                "alg": "HS256",
                "typ": "JWT",
                "sign_type": "SIGN"
            }
        )
        
        return token
        
    except Exception as e:
        raise Exception(f"Failed to generate JWT token: {str(e)}")


def validate_apikey_format(apikey: str) -> bool:
    """
    Validate API key format.
    
    Args:
        apikey: API key string
    
    Returns:
        True if format is valid, False otherwise
    """
    try:
        parts = apikey.split(".", 1)
        return len(parts) == 2 and len(parts[0]) > 0 and len(parts[1]) > 0
    except:
        return False


def get_token_expiry_time(token: str) -> Optional[int]:
    """
    Get token expiry time without verification.
    
    Args:
        token: JWT token string
    
    Returns:
        Expiry timestamp or None if invalid
    """
    try:
        # Decode without verification to get payload
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("exp")
    except:
        return None


def is_token_expired(token: str) -> bool:
    """
    Check if token is expired.
    
    Args:
        token: JWT token string
    
    Returns:
        True if expired, False otherwise
    """
    try:
        exp_time = get_token_expiry_time(token)
        if exp_time is None:
            return True
        
        current_time = int(time.time())
        return current_time >= exp_time
    except:
        return True