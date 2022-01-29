from datetime import datetime
from typing import Optional
from bson import ObjectId
import config


async def check_if_data_is_free_for_registration(email: str, phone: str):
    user_email_check = config.db.users.find_one({"email": email})
    user_phone_check = config.db.users.find_one({"phone": phone})
    if user_email_check is not None or user_phone_check is not None:
        return False
    return True


async def check_user_email_password_in_db(email_or_phone_or_id: str, _id_check: Optional[bool] = False):
    user_email_check = config.db.users.find_one({"email": email_or_phone_or_id})
    user_phone_check = config.db.users.find_one({"phone": email_or_phone_or_id})

    if user_email_check is not None:
        return user_email_check
    elif user_phone_check is not None:
        return user_phone_check
    elif _id_check:
        user__id_check = config.db.users.find_one({"_id": ObjectId(email_or_phone_or_id)})
        if user__id_check is not None:
            return user__id_check
    return None


async def update_last_login(current_user_id: str, user_agent_header: str):
    config.db.users.update_one(
                    {"_id": ObjectId(current_user_id)},
                    {
                        '$push': {
                            "login_info": {"date": (datetime.now()).strftime("%d.%m.%Y %H:%M:%S"),
                                           "user_agent_header": user_agent_header
                                           }
                        },
                        '$set': {"recent_change": str(datetime.now().timestamp()).replace('.', '')}
                    }
                )


async def delete_object_ids_from_dict(the_dict: dict):
    for elem in the_dict.keys():
        if isinstance(the_dict[elem], ObjectId):
            the_dict[elem] = str(the_dict[elem])
    return the_dict
