from datetime import datetime
from typing import Optional
from bson import ObjectId
from pymongo import ReturnDocument
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


async def check_user_session_in_db(session_id: str):
    if len(session_id) == 24:
        user_obj = list(config.db.users.aggregate(
            [{"$unwind": "$login_info"},
             {"$match": {"login_info._id": ObjectId(session_id), "login_info.is_active": True}}]))
        if len(user_obj) > 0:
            return user_obj[0]
    return False


async def unset_active_session_in_db(user_id: str, session_id: str):
    config.db.users.update_one({"_id": ObjectId(user_id),
                                "login_info._id": ObjectId(session_id)},
                               {'$set': {"login_info.$.is_active": False,
                                         "recent_change": str(datetime.now().timestamp()).replace('.', '')}})


async def update_last_login(current_user_id: str, user_agent_header: str):
    active_sessions = list(config.db.users.aggregate(
        [
            {
                "$project": {
                    "_id": ObjectId(current_user_id), "is_active":
                        {"$filter": {"input": "$login_info",
                                              "as": "login",
                                              "cond": {
                                                  "$eq": [
                                                      "$$login.is_active",
                                                      True]}}}}}]))[0]

    if active_sessions['is_active'] is not None and len(active_sessions['is_active']) >= 5:
        await unset_active_session_in_db(current_user_id, active_sessions['is_active'][0]["_id"])

    elem = config.db.users.find_one_and_update(
                    {"_id": ObjectId(current_user_id)},
                    {
                        '$push': {
                            "login_info": {"_id": ObjectId(),
                                           "date": (datetime.now()).strftime("%d.%m.%Y %H:%M:%S"),
                                           "user_agent_header": user_agent_header,
                                           "is_active": True
                                           }
                        },
                        '$set': {"recent_change": str(datetime.now().timestamp()).replace('.', '')}
                    }, return_document=ReturnDocument.AFTER
                )

    return str(elem["login_info"][-1]["_id"])


async def delete_object_ids_from_dict(the_dict: dict):
    for elem in the_dict.keys():
        if isinstance(the_dict[elem], ObjectId):
            the_dict[elem] = str(the_dict[elem])
    return the_dict
