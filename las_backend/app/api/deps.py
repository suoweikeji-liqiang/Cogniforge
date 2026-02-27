from fastapi import Depends, HTTPException, status

from app.models.entities.user import User
from app.api.routes.auth import get_current_user


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user
