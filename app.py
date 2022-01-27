import asyncio

from fastapi import FastAPI, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from uvicorn import Config, Server
import pymysql
from typing import Optional
from pydantic import BaseModel
from bson.objectid import ObjectId
from starlette.responses import FileResponse
import aiohttp
import json
from pprint import pprint
import re
from transliterate import translit
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot, types, md
import datetime
import config


API_KEY = config.FAST_API_KEY
API_KEY_NAME = config.FAST_API_KEY_NAME

api_key_header_auth = APIKeyHeader(name=API_KEY_NAME, auto_error=True)


class ItemExcelOrders(BaseModel):
    user_id: Optional[str] = None
    order_id: Optional[str] = None


class ItemExcelPaymentHistory(BaseModel):
    user_id: str


class ItemFindUserByInfo(BaseModel):
    info: str


class ItemUpdateTgStatus(BaseModel):
    tg_status: str
    telegram_id: str


class ItemCreate(BaseModel):
    user_id: str
    order_id: str
    time: int


class ItemInformAdminSomeMessage(BaseModel):
    text: str
    check_last_message_time: Optional[bool] = False


class Address(BaseModel):
    region: Optional[str] = None
    town: Optional[str] = None
    street: Optional[str] = None
    house: Optional[str] = None
    appartment: Optional[str] = None
    cadastral: Optional[str] = None
    house_internal_building: Optional[str] = "Не указан"
    house_internal_number: Optional[str] = "Не указан"
    house_internal_letter: Optional[str] = "Не указан"


class AddressWhole(BaseModel):
    region: Optional[str] = None
    town: str
    street: str
    house: str
    cadastral: str
    house_internal_number: str
    house_internal_letter: str
    house_internal_building: str


class AddressFirstAndLastAppartment(BaseModel):
    region: Optional[str] = None
    town: str
    street: str
    house: str
    flats_str: Optional[str] = None
    rooms_str: Optional[str] = None
    cadastral: str
    house_internal_number: str
    house_internal_letter: str
    house_internal_building: str


class ItemGoogleMaps(BaseModel):
    text: str
    from_cadastral:  Optional[bool] = False


class ItemFindAndDelete(BaseModel):
    id: str


class ItemInformAdminNotEnoughBalance(BaseModel):
    non_res_areas_str: Optional[str] = None
    res_areas_str: Optional[str] = None
    user_chat_id: Optional[str] = None
    formatted_address: Optional[str] = None
    street: str
    town: str
    house: str
    region: Optional[str] = None
    cadastral: str
    house_internal_letter: str
    house_internal_number: str
    house_internal_building: str
    user_text: str
    google_res: str
    type_of_order: str


class ItemInformAdminBadAddress(BaseModel):
    town: Optional[str] = "Не указано"
    street: Optional[str] = "Не указано"
    region: Optional[str] = "Не указано"
    house: Optional[str] = "Не указано"
    flats: Optional[str] = "Не указано"
    non_residential_flats: Optional[str] = "Не указано"
    house_internal_number: Optional[str] = "Не указано"
    house_internal_letter: Optional[str] = "Не указано"
    house_internal_building: Optional[str] = "Не указано"
    cadastral: Optional[str] = "Не указано"
    user_id: str
    order_id: str
    is_in_addresses_db: Optional[bool] = False
    percent: Optional[float] = 0


async def get_api_key(api_key_header: str = Security(api_key_header_auth)):
    if api_key_header != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key",
        )


def has_cyrillic(text):
    return bool(re.search('[\u0400-\u04FF]', text))


async def get_region_from_cadastral(cadastral):
    region_id = int(cadastral.split(':')[0])
    region = config.regions_for_cadastral[region_id]
    return region


async def check_last_message_time():
    try:
        connection = pymysql.connect(
            host=config.host,
            port=3306,
            user=config.user,
            password=config.password,
            database=config.db_name,
            cursorclass=pymysql.cursors.DictCursor
        )
        try:
            with connection.cursor() as cursor:
                select_row = f"SELECT * FROM `last_message_time` WHERE id = 1;"
                cursor.execute(select_row)
                row = cursor.fetchone()
        finally:
            connection.close()
    except Exception as ex:
        print("Connection refused...")
        print(ex)
        raise HTTPException(status_code=500, detail="Could not connect to mysql")
    if row is not None and datetime.datetime.now() >= row['message_time'] + datetime.timedelta(minutes=120):
        try:
            connection = pymysql.connect(
                host=config.host,
                port=3306,
                user=config.user,
                password=config.password,
                database=config.db_name,
                cursorclass=pymysql.cursors.DictCursor
            )
            try:
                with connection.cursor() as cursor:
                    query = f"UPDATE `last_message_time` SET message_time = " \
                            f"'{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}' WHERE id = 1;"
                    cursor.execute(query)
                    connection.commit()
            finally:
                connection.close()
        except Exception as ex:
            print("Connection refused...")
            print(ex)
            raise HTTPException(status_code=500, detail="Could not connect to mysql")
        return True
    return False


app = FastAPI()


@app.get("/check/one", dependencies=[Security(get_api_key)])
async def post(item: Address):
    data = item.dict()
    print(data)
    town = data['town']
    region = data['region']
    house = data['house']
    appartment = data['appartment']
    cadastral = data['cadastral']
    house_internal_letter = data['house_internal_letter']
    house_internal_number = data['house_internal_number']
    house_internal_building = data['house_internal_building']
    street_type, street_name = None, None
    if data['street'] is not None:
        street = data['street'].split()
        for street_type in config.street_types:
            flag = False
            for id_street_full in range(len(street)):
                if street[id_street_full].lower() == street_type:
                    street_type = street[id_street_full].lower()
                    street.pop(id_street_full)
                    street_name = str()
                    for elem in street:
                        street_name += f'{elem.lower()} '
                    street_name = street_name[:-1]
                    flag = True
                    break
            if flag:
                break
    if ((street_type is None or street_name is None) and cadastral is None) \
            or (town is None and house is None and data['street'] is None and cadastral is None):
        raise HTTPException(status_code=400, detail="Not enough info")
    if cadastral is not None:
        item = await request_with_cadastral(cadastral)
        if len(item['elements']) != 0:
            address = item['elements'][0]['address']['readableAddress'] \
                .replace('.', ' ') \
                .replace(' корпус', ' корп ') \
                .replace(' квартира', ' кв ') \
                .replace(' помещение', ' пом ') \
                .replace(' строение', " строен ") \
                .replace(' домовладение', " д ") \
                .replace(' двлд', " д ") \
                .replace(' вл', " д ") \
                .replace(' дом', ' д ') \
                .replace('  ', ' ')
            address_splitted = [elem.lower() for elem in address.split(', ')]
            elem_in_address = list()
            [[elem_in_address.append(in_elem.lower()) for in_elem in elem.split()] for elem in
             address_splitted]
            if "кв" not in elem_in_address and "пом" not in elem_in_address:
                raise HTTPException(status_code=406, detail="Did not find an apartment in the request")
            return dict(address=address, cadastral=item['elements'][0]['cadNumber'],
                        street='Не указан', house='Не указан',
                        town='Не указан', appartment=item['elements'][0]['address']['apartment'],
                        region=item['elements'][0]['address']['region'])
        raise HTTPException(status_code=404, detail="Item not found")
    to_add = ''
    if house_internal_letter != "Не указан":
        to_add += f' лит {house_internal_letter},'
    if house_internal_number != "Не указан":
        to_add += f' корп {house_internal_number},'
    if house_internal_building != "Не указан":
        to_add += f' строен {house_internal_building},'
    add_region = ''
    non_residential_try_list = list()
    appartment = appartment.lower()
    if region is not None:
        add_region = f'{region}, '
    if appartment.isdigit():
        print_apartment = f'кв {appartment}'
    else:
        print_apartment = f'пом {appartment}'
        non_residential_try_list.append(appartment)

    params = {"term": f"{add_region}{town}, {street_name}, д {house},{to_add} {print_apartment}"}
    try_id = 0
    while True:
        try_id += 1
        if try_id == 5:
            raise HTTPException(status_code=503, detail="Could not connect to rosreestr")
        print(params)
        await asyncio.sleep(0.1)
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=64, ssl=False)) as session:  # [3]
            async with session.get('https://lk.rosreestr.ru/account-back/address/search', params=params) as resp:  # [4]
                if resp.status == 200:
                    response = json.loads(await resp.text())  # [5]
                    if len(response) != 0:
                        info = list()
                        for item in response:
                            address = item['full_name'] \
                                .replace('.', ' ') \
                                .replace(' корпус', ' корп ') \
                                .replace(' квартира', ' кв ') \
                                .replace(' помещение', ' пом ') \
                                .replace(' строение', " строен ") \
                                .replace(' домовладение', " д ") \
                                .replace(' двлд', " д ") \
                                .replace(' вл', " д ") \
                                .replace(' дом', ' д ') \
                                .replace('  ', ' ')
                            cadastral = item["cadnum"]
                            address_splitted = [elem.lower() for elem in address.split(', ')]
                            elem_in_address = list()
                            [[elem_in_address.append(in_elem.lower()) for in_elem in elem.split()] for elem in
                             address_splitted]
                            if 'д' in elem_in_address \
                                    and elem_in_address[elem_in_address.index("д") + 1] == house.lower() \
                                    and (('кв' in elem_in_address
                                          and elem_in_address[elem_in_address.index("кв") + 1] == appartment.lower())
                                         or ('пом' in elem_in_address
                                             and elem_in_address[elem_in_address.index("пом") + 1]
                                             == appartment.lower())) \
                                    and await check_letter_number_building(address, house_internal_letter,
                                                                           house_internal_number,
                                                                           house_internal_building)\
                                    and int(cadastral.split(':')[2]) != 0:
                                for elem in address_splitted[::-1]:
                                    elem_splitted = elem.split()
                                    if len(elem_splitted) > 1:
                                        if elem_splitted[0].lower() == 'д':
                                            house = elem_splitted[1]
                                        elif elem_splitted[1].lower() == 'д':
                                            house = elem_splitted[0]
                                item_info = dict(address=address, cadastral=cadastral, street="Не указан",
                                                 house="Не указан",
                                                 town="Не указан", appartment=appartment,
                                                 region=await get_region_from_cadastral(cadastral))
                                if item_info not in info:
                                    info.append(item_info)
                        if len(info) != 0:
                            if len(info) == 1:
                                return info[0]
                            elif len(info) <= 3:
                                address_list = [address['address'] for address in info]
                                cadastral_list = [cadastral['cadastral'] for cadastral in info]
                                return dict(cadastral=cadastral_list, address_list=address_list, street="Не указан",
                                            house="Не указан",
                                            town="Не указан", appartment=appartment,
                                            region=await get_region_from_cadastral(cadastral))
                            else:
                                raise HTTPException(status_code=400, detail="Too many items")
                    if len(non_residential_try_list) in [1, 2, 3] and appartment.count('н') == 1:
                        try_id = 0
                        if re.sub(r"[^\d]", "", appartment) + '-н' not in non_residential_try_list:
                            appartment = re.sub(r"[^\d]", "", appartment) + '-н'
                        elif re.sub(r"[^\d]", "", appartment) + 'н' not in non_residential_try_list:
                            appartment = re.sub(r"[^\d]", "", appartment) + 'н'
                        elif re.sub(r"[^\d]", "", appartment) + ' н' not in non_residential_try_list:
                            appartment = re.sub(r"[^\d]", "", appartment) + ' н'

                        non_residential_try_list.append(appartment)
                        params = {"term": f"{add_region}{town}, {street_name}, д {house},{to_add} пом {appartment}"}
                        continue
                    if not house.replace(" ", "").isdigit() and not house.replace(" ", "")[-1].isdigit() \
                            and house_internal_letter == "Не указан":
                        try_id = 0
                        house_internal_letter = house[-1]
                        house = house[:-1]
                        to_add += f' лит {house_internal_letter},'
                        if appartment.isdigit():
                            print_apartment = f'кв {appartment}'
                        else:
                            print_apartment = f'пом {appartment}'
                            non_residential_try_list = list()
                            non_residential_try_list.append(appartment)

                        params = {"term": f"{add_region}{town}, {street_name}, д {house},{to_add} {print_apartment}"}
                        continue
                    elif not house.replace(" ", "").isdigit() and house.replace(" ", "")[-1].isdigit()\
                            and house_internal_number == "Не указан":
                        try_id = 0
                        house_internal_number = house[-1]
                        house = house[:-2]
                        to_add += f' корп {house_internal_number},'
                        if appartment.isdigit():
                            print_apartment = f'кв {appartment}'
                        else:
                            print_apartment = f'пом {appartment}'
                            non_residential_try_list = list()
                            non_residential_try_list.append(appartment)

                        params = {"term": f"{add_region}{town}, {street_name}, д {house},{to_add} {print_apartment}"}
                        continue

                    raise HTTPException(status_code=404, detail="Item not found")


@app.get("/check/many", dependencies=[Security(get_api_key)])
async def post(item: Address):
    data = item.dict()
    print(data)
    town = data['town']
    house = data['house']
    region = data['region']
    cadastral = data['cadastral']
    house_internal_letter = data['house_internal_letter']
    house_internal_number = data['house_internal_number']
    house_internal_building = data['house_internal_building']
    street_type, street_name = None, None
    if data['street'] is not None:
        street = data['street'].split()
        for street_type in config.street_types:
            flag = False
            for id_street_full in range(len(street)):
                if street[id_street_full].lower() == street_type:
                    street_type = street[id_street_full].lower()
                    street.pop(id_street_full)
                    street_name = str()
                    for elem in street:
                        street_name += f'{elem.lower()} '
                    street_name = street_name[:-1]
                    flag = True
                    break
            if flag:
                break
    if ((street_type is None or street_name is None) and cadastral is None) \
            or (town is None and house is None and data['street'] is None and cadastral is None):
        raise HTTPException(status_code=400, detail="Not enough info")
    if cadastral is not None:
        item = await request_with_cadastral(cadastral)
        pprint(item)
        if len(item['elements']) != 0:
            address = item['elements'][0]['address']['readableAddress'] \
                .replace('.', ' ') \
                .replace(' корпус', ' корп ') \
                .replace(' квартира', ' кв ') \
                .replace(' помещение', ' пом ') \
                .replace(' строение', " строен ") \
                .replace(' домовладение', " д ") \
                .replace(' двлд', " д ") \
                .replace(' вл', " д ") \
                .replace(' дом', ' д ') \
                .replace('  ', ' ')
            address_splitted = [elem.lower() for elem in address.split(', ')]
            elem_in_address = list()
            [[elem_in_address.append(in_elem.lower()) for in_elem in elem.split()] for elem in
             address_splitted]
            for elem in address_splitted[::-1]:
                elem_splitted = elem.split()
                if len(elem_splitted) > 1:
                    if elem_splitted[0].lower() == 'д':
                        house = elem_splitted[1]
                    elif elem_splitted[1].lower() == 'д':
                        house = elem_splitted[0]
            address_splitted_ = [elem for elem in address.split(', ')]
            if len(address_splitted) > 1 and (address_splitted_[-1].split()[0].lower() == 'кв'
                                              or address_splitted_[-1].split()[0].lower() == 'пом'
                                              or address_splitted_[-1].split()[0].lower() == 'к'):
                address_splitted_.pop(-1)
            address = ', '.join([x for x in address_splitted_])
            for elem in address_splitted[::-1]:
                elem_splitted = elem.split()
                if len(elem_splitted) > 1:
                    if elem_splitted[0].lower() == 'корп':
                        house_internal_number = elem_splitted[1]
                    elif elem_splitted[1].lower() == 'корп':
                        house_internal_number = elem_splitted[0]
                    elif elem_splitted[0].lower() == 'литера':
                        house_internal_letter = elem_splitted[1].upper()
                    elif elem_splitted[1].lower() == 'литера':
                        house_internal_letter = elem_splitted[0].upper()
                    elif elem_splitted[0].lower() == 'строен':
                        house_internal_building = elem_splitted[1]
                    elif elem_splitted[1].lower() == 'строен':
                        house_internal_building = elem_splitted[0]
                    elif elem_splitted[0].lower() == 'д':
                        house = elem_splitted[1]
                    elif elem_splitted[1].lower() == 'д':
                        house = elem_splitted[0]
            params = {"text": address,
                      "from_cadastral": True}
            headers = {API_KEY_NAME: API_KEY}
            async with aiohttp.ClientSession() as session:  # [3]
                async with session.post(f'{config.api_python_link}/get_address_from_google',
                                        json=params, headers=headers) as resp:  # [4]
                    response = json.loads(await resp.text())  # [5]
                    if resp.status == 200:
                        if response['country'] == 'Россия':
                            region = response['region']
                            street = response['street']
                            if house is None:
                                house = response['house']
                            town = response['town']

                            return dict(address=address, cadastral=item['elements'][0]['cadNumber'],
                                        house_internal_number=house_internal_number,
                                        house_internal_building=house_internal_building,
                                        house_internal_letter=house_internal_letter,
                                        house=house,
                                        street=street,
                                        region=region,
                                        town=town
                                        )
                    if resp.status == 404:
                        resp.status = 418
                    elif resp.status == 400:
                        resp.status = 406
                    raise HTTPException(status_code=resp.status,
                                        detail=f"error from /get_address_from_google: {response['detail']}")
        raise HTTPException(status_code=404, detail="Item not found")

    to_add = ''
    if house_internal_letter != "Не указан":
        to_add += f' лит {house_internal_letter},'
    if house_internal_number != "Не указан":
        to_add += f' корп {house_internal_number},'
    if house_internal_building != "Не указан":
        to_add += f' строен {house_internal_building},'
    add_region = ''
    if region is not None:
        add_region = f'{region}, '
    params = {"term": f"{add_region}{town}, {street_name}, д {house},{to_add} кв"}
    try_id = 0
    changed = False
    while True:
        try_id += 1
        if try_id == 5:
            raise HTTPException(status_code=503, detail="Could not connect to rosreestr")
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=64, ssl=False)) as session:  # [3]
            print(params)
            async with session.get('https://lk.rosreestr.ru/account-back/address/search', params=params) as resp:  # [4]
                response = json.loads(await resp.text())  # [5]
                if resp.status == 200:
                    if len(response) != 0:
                        for item in response:
                            address = item['full_name']\
                                .replace('.', ' ')\
                                .replace(' корпус', ' корп ')\
                                .replace(' квартира', ' кв ')\
                                .replace(' помещение', ' пом ')\
                                .replace(' строение', " строен ") \
                                .replace(' домовладение', " д ") \
                                .replace(' двлд', " д ") \
                                .replace(' вл', " д ") \
                                .replace(' дом', ' д ') \
                                .replace('  ', ' ')
                            cadastral = item["cadnum"]
                            address_splitted = [elem.lower() for elem in address.split(', ')]
                            elem_in_address = list()
                            [[elem_in_address.append(in_elem.lower()) for in_elem in elem.split()] for elem in
                             address_splitted]
                            if 'д' in elem_in_address \
                                    and elem_in_address[elem_in_address.index("д") + 1] == house.lower() \
                                    and (('кв' in elem_in_address)
                                         or ('к' in elem_in_address)
                                         or ('пом' in elem_in_address))\
                                    and await check_letter_number_building(address, house_internal_letter,
                                                                           house_internal_number,
                                                                           house_internal_building)\
                                    and int(cadastral.split(':')[2]) != 0:

                                address_splitted_ = [elem for elem in address.split(', ')]
                                if len(address_splitted) > 1 and (address_splitted_[-1].split()[0].lower() == 'кв'
                                                                  or address_splitted_[-1].split()[0].lower() == 'пом'
                                                                  or address_splitted_[-1].split()[0].lower() == 'к'):
                                    address_splitted_.pop(-1)
                                address = ', '.join([x for x in address_splitted_])
                                for elem in address_splitted[::-1]:
                                    elem_splitted = elem.split()
                                    if len(elem_splitted) > 1:
                                        if elem_splitted[0].lower() == 'корп':
                                            house_internal_number = elem_splitted[1]
                                        elif elem_splitted[1].lower() == 'корп':
                                            house_internal_number = elem_splitted[0]
                                        elif elem_splitted[0].lower() == 'литера':
                                            house_internal_letter = elem_splitted[1].upper()
                                        elif elem_splitted[1].lower() == 'литера':
                                            house_internal_letter = elem_splitted[0].upper()
                                        elif elem_splitted[0].lower() == 'строен':
                                            house_internal_building = elem_splitted[1]
                                        elif elem_splitted[1].lower() == 'строен':
                                            house_internal_building = elem_splitted[0]
                                        elif elem_splitted[0].lower() == 'д':
                                            house = elem_splitted[1]
                                        elif elem_splitted[1].lower() == 'д':
                                            house = elem_splitted[0]
                                return dict(address=address, cadastral=cadastral,
                                            house_internal_number=house_internal_number,
                                            house_internal_building=house_internal_building,
                                            house_internal_letter=house_internal_letter,
                                            house=house,
                                            street=data['street'],
                                            region=region,
                                            town=town
                                            )
                    if not changed:
                        params = {"term": f"{add_region}{town}, {street_name}, д {house},{to_add} пом"}
                        changed = True
                        continue
                    if not house.replace(" ", "").isdigit() and not house.replace(" ", "")[-1].isdigit()\
                            and house_internal_letter == "Не указан":
                        house_internal_letter = house[-1]
                        house = house[:-1]
                        to_add += f' лит {house_internal_letter},'
                        params = {"term": f"{add_region}{town}, {street_name}, д {house},{to_add} кв"}
                        changed = False
                        continue
                    elif not house.replace(" ", "").isdigit() and house.replace(" ", "")[-1].isdigit() \
                            and house_internal_number == "Не указан":
                        house_internal_number = house[-1]
                        house = house[:-2]
                        to_add += f' корп {house_internal_number},'
                        params = {"term": f"{add_region}{town}, {street_name}, д {house},{to_add} кв"}
                        changed = False
                        continue
                    raise HTTPException(status_code=404, detail="Item not found")


@app.get("/check/last_and_first_apartment", dependencies=[Security(get_api_key)])
async def post(item: AddressFirstAndLastAppartment):
    data = item.dict()
    print(data)
    town = data['town']
    region = data['region']
    street = data['street']
    house = data['house']
    cadastral = data['cadastral']
    house_internal_number = data['house_internal_number']
    house_internal_letter = data['house_internal_letter']
    house_internal_building = data['house_internal_building']
    flats_str = data['flats_str']
    rooms_str = data['rooms_str']
    street = street.split()
    street_type, street_name = None, None
    last_room_bool, first_room_bool, last_apartment_bool, first_apartment_bool = False, False, False, False
    first_apartment, first_room = None, None
    for street_type in config.street_types:
        flag = False
        for id_street_full in range(len(street)):
            if street[id_street_full].lower() == street_type:
                street_type = street[id_street_full].lower()
                street.pop(id_street_full)
                street_name = str()
                for elem in street:
                    street_name += f'{elem.lower()} '
                street_name = street_name[:-1]
                flag = True
                break
        if flag:
            break
    if street_type is None or street_name is None:
        raise HTTPException(status_code=404, detail="Street not found")
    if flats_str is not None:
        the_list = list()
        [[the_list.append(int(in_elem)) for in_elem in elem.split('-') if in_elem not in the_list] for elem in
         flats_str.split('; ')]
        the_list.sort()
        last_apartment = the_list[-1]
        first_apartment = the_list[0]
        first_apartment_bool = await check_apartment(cadastral, town, street_name, house,
                                                     str(first_apartment),
                                                     house_internal_letter, house_internal_number,
                                                     house_internal_building)
        last_apartment_bool = await check_apartment(cadastral, town, street_name, house,
                                                    str(last_apartment),
                                                    house_internal_letter, house_internal_number,
                                                    house_internal_building)
    if rooms_str is not None:
        the_list = list()
        [[the_list.append(int(in_elem)) for in_elem in elem.split('-') if in_elem not in the_list] for elem in
         rooms_str.split('; ')]
        the_list.sort()
        last_room = the_list[-1]
        first_room = the_list[0]
        first_room_bool = await check_apartment(cadastral, town, street_name, house,
                                                str(first_room) + "-н",
                                                house_internal_letter, house_internal_number,
                                                house_internal_building)
        last_room_bool = await check_apartment(cadastral, town, street_name, house,
                                               str(last_room) + "-н",
                                               house_internal_letter, house_internal_number,
                                               house_internal_building)

    if first_apartment_bool and last_apartment_bool and (rooms_str is None or (first_room_bool and last_room_bool)):
        await check_one_of_the_apartments_on_wps(town, region, street_type, street_name,
                                                 house, cadastral, house_internal_number,
                                                 house_internal_letter,
                                                 house_internal_building, str(first_apartment))
        return True
    elif first_room_bool and last_room_bool and (flats_str is None or (first_apartment_bool and last_apartment_bool)):
        await check_one_of_the_apartments_on_wps(town, region, street_type, street_name,
                                                 house, cadastral, house_internal_number,
                                                 house_internal_letter,
                                                 house_internal_building, str(first_room) + "-н")
        return True
    raise HTTPException(status_code=404, detail="Item not found")


@app.get("/check/whole_house", dependencies=[Security(get_api_key)])
async def post(item: AddressWhole):
    data = item.dict()
    print(data)
    town = data['town']
    street = data['street']
    house = data['house']
    region = data['region']
    cadastral = data['cadastral']
    house_internal_number = data['house_internal_number']
    house_internal_letter = data['house_internal_letter']
    house_internal_building = data['house_internal_building']
    if region is None:
        params = {'town': town,
                  'street': street,
                  'house': house,
                  'cadastral': cadastral,
                  "house_internal_letter": house_internal_letter,
                  "house_internal_number": house_internal_number,
                  "house_internal_building": house_internal_building
                  }
    else:
        params = {'town': town,
                  'street': street,
                  'house': house,
                  'region': region,
                  'cadastral': cadastral,
                  "house_internal_letter": house_internal_letter,
                  "house_internal_number": house_internal_number,
                  "house_internal_building": house_internal_building
                  }
    street = street.split()
    street_type, street_name = None, None
    for street_type in config.street_types:
        flag = False
        for id_street_full in range(len(street)):
            if street[id_street_full].lower() == street_type:
                street_type = street[id_street_full].lower()
                street.pop(id_street_full)
                street_name = str()
                for elem in street:
                    street_name += f'{elem.lower()} '
                street_name = street_name[:-1]
                flag = True
                break
        if flag:
            break
    if street_type is None or street_name is None:
        raise HTTPException(status_code=404, detail="Street not found")
    last_apartment = await appartments_check(town, street_name, house,
                                             cadastral, house_internal_number, house_internal_letter,
                                             house_internal_building)
    last_room = await rooms_check(town, street_name, house, cadastral,
                                  house_internal_number, house_internal_letter,
                                  house_internal_building)
    if last_apartment is not None:
        await check_one_of_the_apartments_on_wps(town, region, street_type, street_name,
                                                 house, cadastral, house_internal_number,
                                                 house_internal_letter,
                                                 house_internal_building, last_apartment.split('-')[0])
    elif last_room is not None:
        await check_one_of_the_apartments_on_wps(town, region, street_type, street_name,
                                                 house, cadastral, house_internal_number,
                                                 house_internal_letter,
                                                 house_internal_building, f"{last_room.split('-')[0]}-н")
    if last_room is not None or last_apartment is not None:
        if last_apartment is not None:
            params['last_flat'] = last_apartment
        else:
            params['last_flat'] = 'Не указано'
        if last_room is not None:
            params['last_non_residential_flat'] = last_room
        else:
            params['last_non_residential_flat'] = 'Не указано'
        headers = {config.JWT_TOKEN_NAME: config.JWT_TOKEN}
        async with aiohttp.ClientSession() as session_1:  # [3]
            async with session_1.post(f'{config.api_node_link}/address/add', json=params,
                                      headers=headers) as resp_1:  # [4]
                if resp_1.status == 200:
                    print('house created')
                    return dict(last_flat=last_apartment, last_non_residential_flat=last_room)
                else:
                    print('error occurred, house not created')
    raise HTTPException(status_code=404, detail="Last apartment or room not found")


@app.post("/create")
async def post(item: ItemCreate):
    data = item.dict()
    print(data)
    try:
        connection = pymysql.connect(
            host=config.host,
            port=3306,
            user=config.user,
            password=config.password,
            database=config.db_name,
            cursorclass=pymysql.cursors.DictCursor)
        try:
            with connection.cursor() as cursor:
                insert_query = f"INSERT INTO `orders_in_progress` (mongodb_user_id, mongodb_order_id," \
                               f" time_to_done_an_order)" \
                               f" VALUES ('{data['user_id']}', '{data['order_id']}', {data['time']});"
                cursor.execute(insert_query)
                connection.commit()
        finally:
            connection.close()
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"Connection refused...\n {ex}")


@app.get("/not_enough_balance/find", dependencies=[Security(get_api_key)])
async def post(item: ItemFindAndDelete):
    data = item.dict()
    print(data)
    try:
        connection = pymysql.connect(
            host=config.host,
            port=3306,
            user=config.user,
            password=config.password,
            database=config.db_name,
            cursorclass=pymysql.cursors.DictCursor)
        try:
            with connection.cursor() as cursor:
                select_row = f"SELECT * FROM `not_enough_balance` WHERE id={data['id']};"
                cursor.execute(select_row)
                row = cursor.fetchone()
        finally:
            connection.close()
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"Connection refused...\n {ex}")

    return row


@app.delete("/not_enough_balance/delete", dependencies=[Security(get_api_key)])
async def post(item: ItemFindAndDelete):
    data = item.dict()
    print(data)
    try:
        connection = pymysql.connect(
            host=config.host,
            port=3306,
            user=config.user,
            password=config.password,
            database=config.db_name,
            cursorclass=pymysql.cursors.DictCursor)
        try:
            with connection.cursor() as cursor:
                delete_row = f"DELETE FROM `not_enough_balance` WHERE id={data['id']}"
                cursor.execute(delete_row)
                connection.commit()
        finally:
            connection.close()
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"Connection refused...\n {ex}")


@app.get("/orders/make_an_excel", dependencies=[Security(get_api_key)])
async def get(item: ItemExcelOrders):
    data = item.dict()
    user_id = data['user_id']
    order_id = data['order_id']
    files = list()

    def filter_set(order_item_):
        def iterator_func(x):
            if 'Завершена' == x.get("status"):
                return True
            else:
                return False

        return filter(iterator_func, order_item_)

    if user_id is not None and order_id is None:
        order_history = config.db['users'].find_one({'_id': ObjectId(user_id)})['order_history']
        for order_id_in_order_history in order_history:
            order = config.db['orders'].find_one({'_id': ObjectId(order_id_in_order_history['order_id'])})
            if order is not None:
                order = order['order_items']
                order = list(filter_set(order))
                for order_item in order:
                    files.append(dict(file=str(order_item["_id"]), order_id=str(order_id_in_order_history['order_id'])))
        if len(files) > 1:
            return dict(file_name=await make_an_excel(files, user_id))
        elif len(files) == 1:
            return dict(message=await make_an_excel(files, user_id))
        raise HTTPException(status_code=400, detail=f"У вас нет готовых выписок")
    elif user_id is None and order_id is not None:
        order = config.db['orders'].find_one({'_id': ObjectId(order_id)})
        if order['status'] != 'Завершён':
            if order is not None:
                order = order['order_items']
                order = list(filter_set(order))
                for order_item in order:
                    files.append(dict(file=str(order_item["_id"]), order_id=order_id))
            if len(files) > 1:
                return dict(file_name=await make_an_excel(files, order_id))
            elif len(files) == 1:
                return dict(message=await make_an_excel(files, order_id))
            raise HTTPException(status_code=400, detail=f"У вас нет готовых выписок")
        return dict(file_name=f'{config.save_files_path}/files_ready_xlsx/{order_id}.xlsx')
    raise HTTPException(status_code=400, detail=f"Отправьте одно из двух значений")


@app.get("/payment_history/make_an_excel", dependencies=[Security(get_api_key)])
async def get(item: ItemExcelPaymentHistory):
    data = item.dict()
    user_id = data['user_id']
    print(user_id)
    user = config.db['users'].find_one({'_id': ObjectId(user_id)})
    if user is not None:
        payment_history = user['payment_history']
        for payment in payment_history:
            if payment['amount'] > 0:
                payment['amount'] = f'+{payment["amount"]}'
            else:
                payment['amount'] = str(payment["amount"])
        return dict(file_name=await make_an_excel_transactions(payment_history, user_id))
    raise HTTPException(status_code=404, detail='user not found')


@app.get("/download/{file_name}")
async def get(file_name: str):
    order = config.db['orders'].find_one({'_id': ObjectId(file_name)})
    user = config.db['users'].find_one({'_id': ObjectId(file_name)})
    if order is not None or user is not None:
        return FileResponse(f'{config.save_files_path}/files_ready_xlsx/{file_name}.xlsx',
                            media_type='application/octet-stream',
                            filename=f'Отчёт.xlsx')
    raise HTTPException(status_code=404, detail="File not found")


@app.post("/admin/ros-key/check", dependencies=[Security(get_api_key)])
async def post():
    rosreesterkeys = sorted([key for key in config.db['rosreesterkeys'].find({})], key=lambda k: k['balance'])
    task_list = list()
    keys = dict()
    for key_id in range(len(rosreesterkeys)):
        ros_key_object = rosreesterkeys[key_id]
        task_list.append(asyncio.create_task(check_ros_key_balance(ros_key_object)))
        keys[rosreesterkeys[key_id]['key']] = rosreesterkeys[key_id]['balance']
    if len(task_list) != 0:
        try:
            await asyncio.gather(*task_list)
            rosreesterkeys_1 = sorted([key for key in config.db['rosreesterkeys'].find({})], key=lambda k: k['balance'])
            mes = ''
            summary = 0
            for key_id in range(len(rosreesterkeys_1)):
                mes += f"\n{key_id + 1}. <b>Ключ:</b> <code>{rosreesterkeys_1[key_id]['key']}</code>\n" \
                       f"<b>Владелец:</b> {rosreesterkeys_1[key_id]['key_owner']}\n" \
                       f"<b>Баланс:</b> {rosreesterkeys_1[key_id]['balance']}\n" \
                       f"<b>Изменение по сравнению с прерыдущим:</b>" \
                       f" {rosreesterkeys_1[key_id]['balance'] - keys[rosreesterkeys_1[key_id]['key']]}\n\n"
                summary += rosreesterkeys_1[key_id]['balance']
            avg_keys_summary = float('{:.2f}'.format(summary / len(rosreesterkeys_1)))
            return dict(mes=f'Текущий баланс ключей <b>{summary}</b>\n'
                            f'Средний баланс на ключах: <b>{avg_keys_summary}</b>\n'
                            f'\n{mes}')
        except ErrorThatShouldCancelOtherTasks:
            for task in task_list:
                task.cancel()
            raise HTTPException(status_code=503, detail="No connection to rosreestr for 5 times")
    raise HTTPException(status_code=404, detail="Ros-keys not found")


@app.post("/admin/inform/some_message", dependencies=[Security(get_api_key)])
async def post(item: ItemInformAdminSomeMessage):
    data = item.dict()
    print(data)
    if not data['check_last_message_time'] or await check_last_message_time():
        try:
            token = config.TG_TOKEN_ADMIN
            bot = Bot(token=token)
            await bot.send_message(-760942865, f'{data["text"]}')
            await bot.close()
        except Exception as e:
            print(f'SENDING TG_ADMIN_BOT ERROR MESSAGE {e}; MESSAGE TEXT {data["text"]}')
            raise HTTPException(status_code=400,
                                detail=f'SENDING TG_ADMIN_BOT ERROR MESSAGE {e}; MESSAGE TEXT {data["text"]}')
    else:
        print(f'NOT SENDING TG_ADMIN_BOT MESSAGE; MESSAGE TEXT {data["text"]}')
        raise HTTPException(status_code=400, detail=f'NOT SENDING TG_ADMIN_BOT MESSAGE; MESSAGE TEXT {data["text"]}')


@app.post('/admin/inform/not_enough_balance', dependencies=[Security(get_api_key)])
async def post(item: ItemInformAdminNotEnoughBalance):
    data = item.dict()
    print(data)
    res_areas_str = data['res_areas_str']
    non_res_areas_str = data['non_res_areas_str']
    formatted_address = data['formatted_address']
    user_chat_id = data['user_chat_id']
    rosreesterkeys = sorted([key for key in config.db['rosreesterkeys'].find({})], key=lambda k: k['balance'])
    mes = ''
    summary = 0
    for key_id in range(len(rosreesterkeys)):
        mes += f"\n{key_id + 1}. <b>Ключ:</b> <code>{rosreesterkeys[key_id]['key']}</code>\n" \
               f"<b>Владелец:</b> {rosreesterkeys[key_id]['key_owner']}\n" \
               f"<b>Баланс:</b> {rosreesterkeys[key_id]['balance']}\n\n"
        summary += rosreesterkeys[key_id]['balance']
    sum1 = 0
    if res_areas_str is not None:
        areas_str = res_areas_str.split(';')
        for id_area in range(len(areas_str)):
            sum1 += (int(areas_str[id_area].split('-')[1]) - int(areas_str[id_area].split('-')[0])) + 1

    if non_res_areas_str is not None:
        areas_str = non_res_areas_str.split(';')
        for id_area in range(len(areas_str)):
            sum1 += (int(areas_str[id_area].split('-')[1]) - int(areas_str[id_area].split('-')[0])) + 1

    try:
        connection = pymysql.connect(
            host=config.host,
            port=3306,
            user=config.user,
            password=config.password,
            database=config.db_name,
            cursorclass=pymysql.cursors.DictCursor)
        try:
            with connection.cursor() as cursor:
                insert_query = f"INSERT INTO `not_enough_balance` (formatted_address, street," \
                               f" house, town, flats, rooms, region, cadastral, house_internal_letter, " \
                               f"house_internal_number, house_internal_building, user_text, " \
                               f"google_res, type_of_order, order_summary)" \
                               f" VALUES ('{formatted_address}', '{data['street']}', '{data['house']}'," \
                               f"'{data['town']}', '{res_areas_str}', '{non_res_areas_str}', '{data['region']}', " \
                               f"'{data['cadastral']}', '{data['house_internal_letter']}', " \
                               f"'{data['house_internal_number']}', '{data['house_internal_building']}'," \
                               f"'{data['user_text']}', '{data['google_res']}', '{data['type_of_order']}', {sum1});"
                cursor.execute(insert_query)
                insert_id = connection.insert_id()
                connection.commit()
        finally:
            connection.close()
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"Connection refused...\n {ex}")

    need_to_have = sum1 - summary
    try:
        markup = InlineKeyboardMarkup()
        markup.row_width = 1  # Ширина поля кнопок
        balance_ready = InlineKeyboardButton("Баланс пополнен", callback_data='admin_1 ' + user_chat_id + ' '
                                                                              + str(insert_id))
        markup.add(balance_ready)
        user_id = '(user_id: не найден)'
        params = {'telegram_id': str(user_chat_id)}
        token = config.TG_TOKEN_ADMIN
        bot = Bot(token=token)
        headers = {config.JWT_TOKEN_NAME: config.JWT_TOKEN}
        async with aiohttp.ClientSession() as session:  # [3]
            async with session.get(f'{config.api_node_link}/users/find-by-tg-id', json=params,
                                   headers=headers) as resp:  # [4]
                if resp.status == 200:
                    response = json.loads(await resp.text())  # [5]
                    user_id = f'(user_id: {response["user"]["_id"]}) '
                    print(user_id)
        await bot.send_message(-760942865, f'Один из пользователей <b>{user_id}</b>'
                                           f'не смог оформить заказ по адресу '
                                           f'<b>"{md.quote_html(formatted_address)}"</b>.\n\n'
                                           f'Всего в заказе: <b>{sum1}</b>\n\n'
                                           f'Общий баланс на ключах: <b>{summary}</b>\n\n'
                                           f'Минимальное пополнение: <b>{need_to_have}</b>\n\n'
                                           f'Вот список ваших <b>{len(rosreesterkeys)}</b> ключей:\n'
                                           f'{mes}'
                                           f'<b>Нажмите кнопку, когда пополните баланс.</b>',
                               reply_markup=markup, parse_mode=types.ParseMode.HTML)
        await bot.close()
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Blocked by user")


@app.post('/admin/inform/bad_address', dependencies=[Security(get_api_key)])
async def post(item: ItemInformAdminBadAddress):
    data = item.dict()
    for elem in data.keys():
        if data[elem] == "":
            data[elem] = "Не указано"
    town = data['town']
    street = data['street']
    region = data['region']
    house = data['house']
    flats = data['flats']
    non_residential_flats = data['non_residential_flats']
    house_internal_number = data['house_internal_number']
    house_internal_letter = data['house_internal_letter']
    house_internal_building = data['house_internal_building']
    cadastral = data['cadastral']
    user_id = data['user_id']
    order_id = data['order_id']
    is_in_addresses_db = data['is_in_addresses_db']
    percent = data['percent']

    try:
        token = config.TG_TOKEN_ADMIN
        bot = Bot(token=token)
        await bot.send_message(-760942865, f'Заказ одного из пользователей (user_id: <code>{user_id}</code>, '
                                           f'order_id: <code>{order_id}</code>) '
                                           f'был неверно обрботан на <b>{float("{0:.2f}".format(percent))}%</b>.'
                                           f'\nВот данные по адресу из заказа:\n\n'
                                           f'Адрес есть в базе: <b>{is_in_addresses_db}</b>.\n'
                                           f'Город: <b>{town}</b>.\n'
                                           f'Регион: <b>{region}</b>.\n'
                                           f'Улица: <b>{street}</b>.\n'
                                           f'Дом: <b>{house}</b>.\n'
                                           f'Квартиры: <b>"{flats}"</b>.\n'
                                           f'Нежилые: <b>"{non_residential_flats}"</b>.\n'
                                           f'Корпус: <b>{house_internal_number}</b>.\n'
                                           f'Литера: <b>{house_internal_letter}</b>.\n'
                                           f'Строение: <b>{house_internal_building}</b>.\n'
                                           f'Кадастровый квартал: <b>{cadastral}</b>.\n\n\n'
                                           f'Если адреса нет в базе, то пользователь оформлял заказ '
                                           f'не по всем помещениям в доме', parse_mode=types.ParseMode.HTML)
        await bot.close()
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Blocked by user")


@app.get('/admin/statistics', dependencies=[Security(get_api_key)])
async def get():
    rosreesterkeys = list(config.db['rosreesterkeys'].find({}))
    summary_on_keys = 0
    summary_on_users = 0
    for key in rosreesterkeys:
        summary_on_keys += key['balance']
    users = list(config.db['users'].find({}))
    for user in users:
        summary_on_users += user['balance']

    def filter_set(user_):
        def iterator_func(x):
            if x.get("email") == "" or x.get("email").lower() == "не указан":
                return True
            else:
                return False

        return filter(iterator_func, user_)

    users_with_emailnull = len(list(filter_set(users)))

    def filter_set(user_):
        def iterator_func(x):
            if x.get('emailVerified') and x.get("email") != "" and x.get("email").lower() != "не указан":
                return True
            else:
                return False

        return filter(iterator_func, user_)

    users_with_emailverified = len(list(filter_set(users)))

    def filter_set(user_):
        def iterator_func(x):
            if not x.get('emailVerified') and x.get("email") != "" and x.get("email").lower() != "не указан":
                return True
            else:
                return False

        return filter(iterator_func, user_)

    users_with_notemailverified = len(list(filter_set(users)))

    def filter_set(user_):
        def iterator_func(x):
            if x.get('newsletter'):
                return True
            else:
                return False

        return filter(iterator_func, user_)

    users_with_newsletter = len(list(filter_set(users)))

    def filter_set(user_):
        def iterator_func(x):
            if x.get('tg_status') == 'kicked':
                return True
            else:
                return False

        return filter(iterator_func, user_)

    blocked_users = list(filter_set(users))

    def filter_set(order):
        def iterator_func(x):
            if x.get('status') != "Завершён":
                return True
            else:
                return False

        return filter(iterator_func, order)
    orders = list(config.db['orders'].find({}))
    orders_not_done_yet = list(filter_set(orders))
    orders_today = list()
    [[orders_today.append(item) for item in user_['order_history']
      if datetime.datetime.strptime(item['date'], "%d.%m.%Y %H:%M:%S") >=
      datetime.datetime.combine((datetime.datetime.now() + datetime.timedelta(hours=3)).date(),
                                datetime.datetime.min.time())]for user_ in users]
    order_items = list()
    [[order_items.append(order_item) for order_item in order['order_items']] for order in orders]
    avg_amount_of_order_items = float('{:.2f}'.format(len(order_items) / len(orders)))

    def filter_set(address_):
        def iterator_func(x):
            if not x.get('failed_verification'):
                return True
            else:
                return False

        return filter(iterator_func, address_)

    addresses = list(config.db['addresses'].find({}))
    count = 0
    for address in addresses:
        if address['last_flat'] != 'Не указано':
            count += int(address['last_flat'].split('-')[1]) - int(address['last_flat'].split('-')[0]) + 1
        if address['last_non_residential_flat'] != 'Не указано':
            count += int(address['last_non_residential_flat'].split('-')[1]) \
                     - int(address['last_non_residential_flat'].split('-')[0]) + 1

    return dict(amount_of_keys=len(rosreesterkeys), amount_of_users=len(users),
                blocked_users=len(blocked_users),
                percent_blocked_users='{:.3%}'.format(
                    len(blocked_users) / len(users)),
                summary_on_users=summary_on_users,
                summary_on_keys=summary_on_keys, orders_not_done_yet=len(orders_not_done_yet),
                amount_of_addresses=len(addresses), amount_of_apartment=count,
                users_with_newsletter=users_with_newsletter, users_with_emailVerified=users_with_emailverified,
                amount_of_orders=len(orders), amount_of_bad_addresses=len(list(filter_set(addresses))),
                avg_amount_of_order_items=avg_amount_of_order_items,
                users_with_notemailVerified=users_with_notemailverified,
                users_with_emailnull=users_with_emailnull,
                avg_keys_summary=float('{:.2f}'.format(summary_on_keys/len(rosreesterkeys))),
                orders_today=len(orders_today))


@app.get('/admin/ros-key/mes', dependencies=[Security(get_api_key)])
async def get():
    rosreesterkeys = sorted([key for key in config.db['rosreesterkeys'].find({})], key=lambda k: k['balance'])
    mes = ''
    summary = 0
    for key_id in range(len(rosreesterkeys)):
        mes += f"\n{key_id + 1}. <b>Ключ:</b> <code>{rosreesterkeys[key_id]['key']}</code>\n" \
               f"<b>Владелец:</b> {rosreesterkeys[key_id]['key_owner']}\n" \
               f"<b>Баланс:</b> {rosreesterkeys[key_id]['balance']}\n\n"
        summary += rosreesterkeys[key_id]['balance']
    avg_keys_summary = float('{:.2f}'.format(summary / len(rosreesterkeys)))
    mes_ = f'<b>Общий баланс на ключах:</b> {summary}\n' \
           f'<b>Средний баланс на ключах:</b> {avg_keys_summary}\n\n' \
           f'Вот список ваших <b>{len(rosreesterkeys)}</b> ключей:\n' \
           f'{mes}'

    return dict(mes=mes_)


@app.get('/admin/promo/mes', dependencies=[Security(get_api_key)])
async def get():
    promocodes = sorted([promo for promo in config.db['promocodes'].find({})], key=lambda k: k['amount'])
    mes = ''
    summary = 0
    count = 0
    for promocode_id in range(len(promocodes)):
        if not promocodes[promocode_id]['isUsed']:
            mes += f"\n{count + 1}. <b>Код:</b> <code>{promocodes[promocode_id]['code']}</code>\n" \
                   f"<b>Количество:</b> {promocodes[promocode_id]['amount']}\n" \
                   f"<b>Ссылка для приглашения:</b> <code>" \
                   f"https://t.me/EGRN_RosreestrInfo_bot?start=" \
                   f"{promocodes[promocode_id]['code']}</code>\n\n"
            summary += promocodes[promocode_id]['amount']
            count += 1
    avg_promos_summary = float('{:.2f}'.format(summary / count))
    mes_ = f'<b>Общее количество на промокодах:</b> {summary}\n' \
           f'<b>Среднее количество на промокоде:</b> {avg_promos_summary}\n\n' \
           f'Вот список ваших <b>{count}</b> промокодов:\n' \
           f'{mes}'

    return dict(mes=mes_)


@app.get('/admin/address-logs/mes', dependencies=[Security(get_api_key)])
async def get():
    address_logs = [address_log for address_log in config.db['addresslogs'].find({})][-10:]
    mes = ''
    count = 0
    for address_log_id in range(len(address_logs)):
        if address_logs[address_log_id]['is_ordered']:
            is_ordered = 'Да'
        else:
            is_ordered = 'Нет'
        mes += f"---------------------" \
               f"\n{len(address_logs) - address_log_id}. " \
               f"Тип заказа: {address_logs[address_log_id]['type_of_order']}\n\n" \
               f"Текст пользователя: {address_logs[address_log_id]['user_text']}\n\n" \
               f"Ответ google: {address_logs[address_log_id]['google_res']}\n\n" \
               f"Ответ Росреестра: {address_logs[address_log_id]['rosreestr_res']}\n\n" \
               f"Ответ Бота: {address_logs[address_log_id]['our_res']}\n\n" \
               f"Заказ оформлен: {is_ordered}\n\n" \
               f"Дата и время: {address_logs[address_log_id]['date']}\n\n" \
               f"user_id: {address_logs[address_log_id]['user_id']}\n" \
               f"---------------------\n\n\n"
        count += 1
    mes_ = f'Вот список ваших {count} последних Адрес логов:\n' \
           f'{mes}'

    return dict(mes=mes_)


@app.get('/admin/find_user', dependencies=[Security(get_api_key)])
async def get(item: ItemFindUserByInfo):
    data = item.dict()
    if len(data['info']) == 24:
        user = config.db['users'].find_one({'_id': ObjectId(data['info'])})
        if user is None:
            raise HTTPException(status_code=404, detail='user not found')
        order_history = user['order_history']
        for elem in order_history:
            elem['_id'] = str(elem['_id'])
            elem['order_id'] = str(elem['order_id'])
        return dict(_id=str(user['_id']), phone_number=user["phone_number"], email=user["email"],
                    emailVerified=user['emailVerified'], newsletter=user['newsletter'], telegram_id=user['telegram_id'],
                    balance=user['balance'], reg_date=user['reg_date'], payment_history=user['payment_history'],
                    order_history=order_history, username=user['username'], tg_status=user['tg_status'])
    user = config.db['users'].find_one({'phone_number': data['info']})
    if user is not None:
        order_history = user['order_history']
        for elem in order_history:
            elem['_id'] = str(elem['_id'])
            elem['order_id'] = str(elem['order_id'])
        return dict(_id=str(user['_id']), phone_number=user["phone_number"], email=user["email"],
                    emailVerified=user['emailVerified'], newsletter=user['newsletter'],
                    telegram_id=user['telegram_id'],
                    balance=user['balance'], reg_date=user['reg_date'], payment_history=user['payment_history'],
                    order_history=order_history, username=user['username'], tg_status=user['tg_status'])
    user = config.db['users'].find_one({'telegram_id': data['info']})
    if user is not None:
        order_history = user['order_history']
        for elem in order_history:
            elem['_id'] = str(elem['_id'])
            elem['order_id'] = str(elem['order_id'])
        return dict(_id=str(user['_id']), phone_number=user["phone_number"], email=user["email"],
                    emailVerified=user['emailVerified'], newsletter=user['newsletter'],
                    telegram_id=user['telegram_id'],
                    balance=user['balance'], reg_date=user['reg_date'], payment_history=user['payment_history'],
                    order_history=order_history, username=user['username'], tg_status=user['tg_status'])
    raise HTTPException(status_code=404, detail='user not found')


@app.get('/admin/find_order', dependencies=[Security(get_api_key)])
async def get(item: ItemFindUserByInfo):
    data = item.dict()
    if len(data['info']) == 24:
        order = config.db['orders'].find_one({'_id': ObjectId(data['info'])})
    else:
        order = config.db['orders'].find_one({'code': data['info']})
    if order is None:
        raise HTTPException(status_code=404, detail='order not found')
    user = config.db['users'].find_one({'order_history.order_id': ObjectId(order['_id'])})
    if user is None:
        raise HTTPException(status_code=404, detail='user not found')
    order_items = order['order_items']
    for elem in order_items:
        elem['_id'] = str(elem['_id'])

    def filter_set(order_item, status):
        def iterator_func(x):
            if x.get('status') == status:
                return True
            else:
                return False

        return filter(iterator_func, order_item)

    order_history = user['order_history']
    for elem in order_history:
        elem['_id'] = str(elem['_id'])
        elem['order_id'] = str(elem['order_id'])

    if 'code' in order:
        order_code = order['code']
    else:
        order_code = 'Отсутсвует'

    if 'date' in order:
        order_date = order['date']
    else:
        order_date = "Не указано"

    return dict(
        _id=str(user['_id']), phone_number=user["phone_number"], email=user["email"],
        emailVerified=user['emailVerified'], newsletter=user['newsletter'], telegram_id=user['telegram_id'],
        balance=user['balance'], reg_date=user['reg_date'],
        username=user['username'], order_code=order_code,
        object_address=order['object_address'],
        town=order['town'], order_id=str(order['_id']),
        street=order['street'],
        region=order['region'],
        house=order['house'],
        flats=order['flats'], order_date=order_date,
        non_residential_flats=order['non_residential_flats'],
        status=order['status'],
        house_internal_number=order['house_internal_number'],
        house_internal_building=order['house_internal_building'],
        house_internal_letter=order['house_internal_letter'],
        cadastral=order['cadastral'],
        order_items=order_items,
        order_items_done=list(filter_set(order_items, 'Завершена')),
        percent_order_items_done='{:.3%}'.format(len(list(
            filter_set(order_items, 'Завершена'))) / len(order_items)),
        order_items_not_found=list(filter_set(order_items, 'Не найден')),
        percent_order_not_found='{:.3%}'.format(len(list(
            filter_set(order_items, 'Не найден'))) / len(order_items)),
        payment_history=user['payment_history'],
        order_history=order_history
    )


@app.post('/users/update-tg-status', dependencies=[Security(get_api_key)])
async def get(item: ItemUpdateTgStatus):
    data = item.dict()
    user = config.db['users'].find_one({'telegram_id': data['telegram_id']})
    if user is not None:
        config.db['users'].update_one({'telegram_id': data['telegram_id']},
                                      {'$set': {'tg_status': data['tg_status'],
                                                'recent_change':
                                                    str(datetime.datetime.now().timestamp()).replace('.', '')}})
        return True
    raise HTTPException(status_code=404, detail='user not found')


@app.get('/admin/statistics/get_address_logs_by_user', dependencies=[Security(get_api_key)])
async def get(item: ItemFindUserByInfo):
    data = item.dict()
    params = {"info": data['info']}
    headers = {API_KEY_NAME: API_KEY}
    async with aiohttp.ClientSession() as session:  # [3]
        async with session.get(f'{config.api_python_link}/admin/find_user',
                               json=params, headers=headers) as resp:  # [4]
            if resp.status != 200:
                raise HTTPException(status_code=404, detail='user not found')
            response = json.loads(await resp.text())
            addresslogs = list(config.db['addresslogs'].find({'user_id': ObjectId(response['_id'])}))
            if addresslogs is None:
                raise HTTPException(status_code=404, detail='user not found')
            if len(addresslogs) == 0:
                return dict(summary_address_logs=0)
            count_order_for_one = 0
            count_order_for_many = 0
            count_order_for_whole = 0
            count_ordered = 0
            count_exit = 0
            count_blocked = 0
            count_not_enough_balance = 0
            count_wrong_address = 0
            count_decided_not_to_order = 0
            count_address_not_found = 0
            count_could_not_count_apartments = 0
            count_internal_server_err = 0
            count_user_not_enough_balance = 0
            count_could_not_coonect_to_rosrrestr = 0
            count_too_many_object = 0
            count_no_apartment_in_address = 0
            count_found_no_area = 0
            count_unknown_error = 0
            count_no_house_in_address = 0
            count_found_address_located_not_in_russia = 0
            count_unknown_error_before_order = 0
            count_too_many_areas = 0
            count_wrong_areas_by_user = 0
            count_user_decided_to_send_different_area = 0
            count_cannot_check_this_address = 0
            count_address_was_not_found_on_google = 0
            unmentioned = 0
            unmentioned_type = list()
            unmentioned_our_res = list()
            for addresslog in addresslogs:
                if addresslog['type_of_order'] == 'Только один':
                    count_order_for_one += 1
                elif addresslog['type_of_order'] == 'Несколько в диапазоне кВ':
                    count_order_for_many += 1
                elif addresslog['type_of_order'] == 'По всему дому':
                    count_order_for_whole += 1
                else:
                    unmentioned_type.append(addresslog['type_of_order'])

                if addresslog['is_ordered']:
                    count_ordered += 1
                elif addresslog['our_res'] == 'Пользователь вышел из меню заказа':
                    count_exit += 1
                elif addresslog['our_res'] == 'Пользователь заблокировал бота':
                    count_blocked += 1
                elif addresslog['our_res'].split('.')[0] == 'На балансе админов не хватало средств для оформления' \
                                                            ' заказа':
                    count_not_enough_balance += 1
                elif addresslog['our_res'] == 'Пользователь пометил адрес как неверный':
                    count_wrong_address += 1
                elif addresslog['our_res'] == 'Пользователь решил не заказывать':
                    count_decided_not_to_order += 1
                elif addresslog['our_res'] == 'Адрес не найден':
                    count_address_not_found += 1
                elif addresslog['our_res'] == 'Не удалось верно подсчитать количество помещений в доме':
                    count_could_not_count_apartments += 1
                elif addresslog['our_res'] == 'На сервере произошла ошибка' \
                        or addresslog['our_res'] == 'Ошибка 500 на сервере':
                    count_internal_server_err += 1
                elif addresslog['our_res'].split('.')[0] in ['На балансе пользователя недостаточно средств',
                                                             'На балансе пользователя не хватало средств']:
                    count_user_not_enough_balance += 1
                elif addresslog['our_res'] == 'Не удалось подключиться к серверам росреестра':
                    count_could_not_coonect_to_rosrrestr += 1
                elif addresslog['our_res'] == 'Найдено слишком много объектов':
                    count_too_many_object += 1
                elif addresslog['our_res'] == 'В адресе не найден квартира':
                    count_no_apartment_in_address += 1
                elif addresslog['our_res'].split(':')[0] == 'В указанном доме нет тех квартир, которые ' \
                                                            'искал пользователь':
                    count_found_no_area += 1
                elif addresslog['our_res'].split('.')[0] == 'Произошла неизвестная ошибка':
                    count_unknown_error += 1
                elif addresslog['our_res'] == 'В адресе не найден дом':
                    count_no_house_in_address += 1
                elif addresslog['our_res'] == 'Найденный адрес расположен не в России':
                    count_found_address_located_not_in_russia += 1
                elif addresslog['our_res'] == 'Неизвестная ошибка перед оформлением заказа':
                    count_unknown_error_before_order += 1
                elif len(addresslog['our_res'].split('.')) > 1 \
                        and addresslog['our_res'].split('.')[1] == 'Слишком много диапазонов':
                    count_too_many_areas += 1
                elif 'Пользователь отправил некорректные данные' in addresslog['our_res']:
                    count_wrong_areas_by_user += 1
                elif addresslog['our_res'] == 'Пользователь решил указать другой диапазон':
                    count_user_decided_to_send_different_area += 1
                elif addresslog['our_res'] == 'Невозможно обработать по этому адресу':
                    count_cannot_check_this_address += 1
                elif addresslog['our_res'] == 'Не удалось найти в google':
                    count_address_was_not_found_on_google += 1
                else:
                    unmentioned += 1
                    unmentioned_our_res.append(addresslog['our_res'])
            return dict(
                user_id=response['_id'],
                summary_address_logs=len(addresslogs),
                count_order_for_one=count_order_for_one,
                percent_of_order_for_one='{:.3%}'.format(
                    count_order_for_one / len(addresslogs)),
                count_order_for_many=count_order_for_many,
                percent_of_order_for_many='{:.3%}'.format(
                    count_order_for_many / len(addresslogs)),
                count_order_for_whole=count_order_for_whole,
                percent_of_order_for_whole='{:.3%}'.format(
                    count_order_for_whole / len(addresslogs)),
                unmentioned_type=unmentioned_type,
                count_ordered=count_ordered,
                percent_of_count_ordered='{:.3%}'.format(
                    count_ordered / len(addresslogs)),
                count_exit=count_exit,
                percent_of_count_exit='{:.3%}'.format(
                    count_exit / len(addresslogs)),
                count_blocked=count_blocked,
                percent_of_count_blocked='{:.3%}'.format(
                    count_blocked / len(addresslogs)),
                count_not_enough_balance=count_not_enough_balance,
                percent_of_count_not_enough_balance='{:.3%}'.format(
                    count_not_enough_balance / len(addresslogs)),
                count_wrong_address=count_wrong_address,
                percent_of_count_wrong_address='{:.3%}'.format(
                    count_wrong_address / len(addresslogs)),
                count_decided_not_to_order=count_decided_not_to_order,
                percent_of_count_decided_not_to_order='{:.3%}'.format(
                    count_decided_not_to_order / len(addresslogs)),
                count_address_not_found=count_address_not_found,
                percent_of_count_address_not_found='{:.3%}'.format(
                    count_address_not_found / len(addresslogs)),
                count_could_not_count_apartments=count_could_not_count_apartments,
                percent_of_count_could_not_count_apartments='{:.3%}'.format(
                    count_could_not_count_apartments / len(addresslogs)),
                count_internal_server_err=count_internal_server_err,
                percent_of_count_internal_server_err='{:.3%}'.format(
                    count_internal_server_err / len(addresslogs)),
                count_user_not_enough_balance=count_user_not_enough_balance,
                percent_of_count_user_not_enough_balance='{:.3%}'.format(
                    count_user_not_enough_balance / len(addresslogs)),
                count_could_not_coonect_to_rosrrestr=count_could_not_coonect_to_rosrrestr,
                percent_of_count_could_not_coonect_to_rosrrestr='{:.3%}'.format(
                    count_could_not_coonect_to_rosrrestr / len(addresslogs)),
                count_too_many_object=count_too_many_object,
                percent_of_count_too_many_object='{:.3%}'.format(
                    count_too_many_object / len(addresslogs)),
                count_no_apartment_in_address=count_no_apartment_in_address,
                percent_of_count_no_apartment_in_address='{:.3%}'.format(
                    count_no_apartment_in_address / len(addresslogs)),
                count_found_no_area=count_found_no_area,
                percent_of_count_found_no_area='{:.3%}'.format(
                    count_found_no_area / len(addresslogs)),
                count_unknown_error=count_unknown_error,
                percent_of_count_unknown_error='{:.3%}'.format(
                    count_unknown_error / len(addresslogs)),
                count_no_house_in_address=count_no_house_in_address,
                percent_of_count_no_house_in_address='{:.3%}'.format(
                    count_no_house_in_address / len(addresslogs)),
                count_found_address_located_not_in_russia=count_found_address_located_not_in_russia,
                percent_of_count_found_address_located_not_in_russia='{:.3%}'.format(
                    count_found_address_located_not_in_russia / len(addresslogs)),
                count_unknown_error_before_order=count_unknown_error_before_order,
                percent_of_count_unknown_error_before_order='{:.3%}'.format(
                    count_unknown_error_before_order / len(addresslogs)),
                count_too_many_areas=count_too_many_areas,
                percent_of_count_too_many_areas='{:.3%}'.format(
                    count_too_many_areas / len(addresslogs)),
                count_wrong_areas_by_user=count_wrong_areas_by_user,
                percent_of_count_wrong_areas_by_user='{:.3%}'.format(
                    count_wrong_areas_by_user / len(addresslogs)),
                count_user_decided_to_send_different_area=count_user_decided_to_send_different_area,
                percent_of_count_user_decided_to_send_different_area='{:.3%}'.format(
                    count_user_decided_to_send_different_area / len(addresslogs)),
                count_cannot_check_this_address=count_cannot_check_this_address,
                percent_of_count_cannot_check_this_address='{:.3%}'.format(
                    count_cannot_check_this_address / len(addresslogs)),
                count_address_was_not_found_on_google=count_address_was_not_found_on_google,
                percent_of_count_address_was_not_found_on_google='{:.3%}'.format(
                    count_address_was_not_found_on_google / len(addresslogs)),
                unmentioned=unmentioned, unmentioned_our_res=unmentioned_our_res
            )
    raise HTTPException(status_code=500, detail='Unknown error')


@app.get('/admin/statistics/get_address_logs_of_all', dependencies=[Security(get_api_key)])
async def get():
    addresslogs = list(config.db['addresslogs'].find({}))
    if addresslogs is None:
        raise HTTPException(status_code=404, detail='user not found')
    if len(addresslogs) == 0:
        return dict(summary_address_logs=0)
    count_order_for_one = 0
    count_order_for_many = 0
    count_order_for_whole = 0
    count_ordered = 0
    count_exit = 0
    count_blocked = 0
    count_not_enough_balance = 0
    count_wrong_address = 0
    count_decided_not_to_order = 0
    count_address_not_found = 0
    count_could_not_count_apartments = 0
    count_internal_server_err = 0
    count_user_not_enough_balance = 0
    count_could_not_coonect_to_rosrrestr = 0
    count_too_many_object = 0
    count_no_apartment_in_address = 0
    count_found_no_area = 0
    count_unknown_error = 0
    count_no_house_in_address = 0
    count_found_address_located_not_in_russia = 0
    count_unknown_error_before_order = 0
    count_too_many_areas = 0
    count_wrong_areas_by_user = 0
    count_user_decided_to_send_different_area = 0
    count_cannot_check_this_address = 0
    count_address_was_not_found_on_google = 0
    unmentioned = 0
    unmentioned_type = list()
    unmentioned_our_res = list()
    for addresslog in addresslogs:
        if addresslog['type_of_order'] == 'Только один':
            count_order_for_one += 1
        elif addresslog['type_of_order'] == 'Несколько в диапазоне кВ':
            count_order_for_many += 1
        elif addresslog['type_of_order'] == 'По всему дому':
            count_order_for_whole += 1
        else:
            unmentioned_type.append(addresslog['type_of_order'])

        if addresslog['is_ordered']:
            count_ordered += 1
        elif addresslog['our_res'] == 'Пользователь вышел из меню заказа':
            count_exit += 1
        elif addresslog['our_res'] == 'Пользователь заблокировал бота':
            count_blocked += 1
        elif addresslog['our_res'].split('.')[0] == 'На балансе админов не хватало средств для оформления' \
                                                    ' заказа':
            count_not_enough_balance += 1
        elif addresslog['our_res'] == 'Пользователь пометил адрес как неверный':
            count_wrong_address += 1
        elif addresslog['our_res'] == 'Пользователь решил не заказывать':
            count_decided_not_to_order += 1
        elif addresslog['our_res'] == 'Адрес не найден':
            count_address_not_found += 1
        elif addresslog['our_res'] == 'Не удалось верно подсчитать количество помещений в доме':
            count_could_not_count_apartments += 1
        elif addresslog['our_res'] == 'На сервере произошла ошибка' \
                or addresslog['our_res'] == 'Ошибка 500 на сервере':
            count_internal_server_err += 1
        elif addresslog['our_res'].split('.')[0] in ['На балансе пользователя недостаточно средств',
                                                     'На балансе пользователя не хватало средств']:
            count_user_not_enough_balance += 1
        elif addresslog['our_res'] == 'Не удалось подключиться к серверам росреестра':
            count_could_not_coonect_to_rosrrestr += 1
        elif addresslog['our_res'] == 'Найдено слишком много объектов':
            count_too_many_object += 1
        elif addresslog['our_res'] == 'В адресе не найден квартира':
            count_no_apartment_in_address += 1
        elif addresslog['our_res'].split(':')[0] == 'В указанном доме нет тех квартир, которые ' \
                                                    'искал пользователь':
            count_found_no_area += 1
        elif addresslog['our_res'].split('.')[0] == 'Произошла неизвестная ошибка':
            count_unknown_error += 1
        elif addresslog['our_res'] == 'В адресе не найден дом':
            count_no_house_in_address += 1
        elif addresslog['our_res'] == 'Найденный адрес расположен не в России':
            count_found_address_located_not_in_russia += 1
        elif addresslog['our_res'] == 'Неизвестная ошибка перед оформлением заказа':
            count_unknown_error_before_order += 1
        elif len(addresslog['our_res'].split('.')) > 1 \
                and addresslog['our_res'].split('.')[1] == 'Слишком много диапазонов':
            count_too_many_areas += 1
        elif 'Пользователь отправил некорректные данные' in addresslog['our_res']:
            count_wrong_areas_by_user += 1
        elif addresslog['our_res'] == 'Пользователь решил указать другой диапазон':
            count_user_decided_to_send_different_area += 1
        elif addresslog['our_res'] == 'Невозможно обработать по этому адресу':
            count_cannot_check_this_address += 1
        elif addresslog['our_res'] == 'Не удалось найти в google':
            count_address_was_not_found_on_google += 1
        else:
            unmentioned += 1
            unmentioned_our_res.append(addresslog['our_res'])
    return dict(
        summary_address_logs=len(addresslogs),
        count_order_for_one=count_order_for_one,
        percent_of_order_for_one='{:.3%}'.format(
            count_order_for_one / len(addresslogs)),
        count_order_for_many=count_order_for_many,
        percent_of_order_for_many='{:.3%}'.format(
            count_order_for_many / len(addresslogs)),
        count_order_for_whole=count_order_for_whole,
        percent_of_order_for_whole='{:.3%}'.format(
            count_order_for_whole / len(addresslogs)),
        unmentioned_type=unmentioned_type,
        count_ordered=count_ordered,
        percent_of_count_ordered='{:.3%}'.format(
            count_ordered / len(addresslogs)),
        count_exit=count_exit,
        percent_of_count_exit='{:.3%}'.format(
            count_exit / len(addresslogs)),
        count_blocked=count_blocked,
        percent_of_count_blocked='{:.3%}'.format(
            count_blocked / len(addresslogs)),
        count_not_enough_balance=count_not_enough_balance,
        percent_of_count_not_enough_balance='{:.3%}'.format(
            count_not_enough_balance / len(addresslogs)),
        count_wrong_address=count_wrong_address,
        percent_of_count_wrong_address='{:.3%}'.format(
            count_wrong_address / len(addresslogs)),
        count_decided_not_to_order=count_decided_not_to_order,
        percent_of_count_decided_not_to_order='{:.3%}'.format(
            count_decided_not_to_order / len(addresslogs)),
        count_address_not_found=count_address_not_found,
        percent_of_count_address_not_found='{:.3%}'.format(
            count_address_not_found / len(addresslogs)),
        count_could_not_count_apartments=count_could_not_count_apartments,
        percent_of_count_could_not_count_apartments='{:.3%}'.format(
            count_could_not_count_apartments / len(addresslogs)),
        count_internal_server_err=count_internal_server_err,
        percent_of_count_internal_server_err='{:.3%}'.format(
            count_internal_server_err / len(addresslogs)),
        count_user_not_enough_balance=count_user_not_enough_balance,
        percent_of_count_user_not_enough_balance='{:.3%}'.format(
            count_user_not_enough_balance / len(addresslogs)),
        count_could_not_coonect_to_rosrrestr=count_could_not_coonect_to_rosrrestr,
        percent_of_count_could_not_coonect_to_rosrrestr='{:.3%}'.format(
            count_could_not_coonect_to_rosrrestr / len(addresslogs)),
        count_too_many_object=count_too_many_object,
        percent_of_count_too_many_object='{:.3%}'.format(
            count_too_many_object / len(addresslogs)),
        count_no_apartment_in_address=count_no_apartment_in_address,
        percent_of_count_no_apartment_in_address='{:.3%}'.format(
            count_no_apartment_in_address / len(addresslogs)),
        count_found_no_area=count_found_no_area,
        percent_of_count_found_no_area='{:.3%}'.format(
            count_found_no_area / len(addresslogs)),
        count_unknown_error=count_unknown_error,
        percent_of_count_unknown_error='{:.3%}'.format(
            count_unknown_error / len(addresslogs)),
        count_no_house_in_address=count_no_house_in_address,
        percent_of_count_no_house_in_address='{:.3%}'.format(
            count_no_house_in_address / len(addresslogs)),
        count_found_address_located_not_in_russia=count_found_address_located_not_in_russia,
        percent_of_count_found_address_located_not_in_russia='{:.3%}'.format(
            count_found_address_located_not_in_russia / len(addresslogs)),
        count_unknown_error_before_order=count_unknown_error_before_order,
        percent_of_count_unknown_error_before_order='{:.3%}'.format(
            count_unknown_error_before_order / len(addresslogs)),
        count_too_many_areas=count_too_many_areas,
        percent_of_count_too_many_areas='{:.3%}'.format(
            count_too_many_areas / len(addresslogs)),
        count_wrong_areas_by_user=count_wrong_areas_by_user,
        percent_of_count_wrong_areas_by_user='{:.3%}'.format(
            count_wrong_areas_by_user / len(addresslogs)),
        count_user_decided_to_send_different_area=count_user_decided_to_send_different_area,
        percent_of_count_user_decided_to_send_different_area='{:.3%}'.format(
            count_user_decided_to_send_different_area / len(addresslogs)),
        count_cannot_check_this_address=count_cannot_check_this_address,
        percent_of_count_cannot_check_this_address='{:.3%}'.format(
            count_cannot_check_this_address / len(addresslogs)),
        count_address_was_not_found_on_google=count_address_was_not_found_on_google,
        percent_of_count_address_was_not_found_on_google='{:.3%}'.format(
            count_address_was_not_found_on_google / len(addresslogs)),
        unmentioned=unmentioned, unmentioned_our_res=unmentioned_our_res
    )


@app.post('/get_address_from_google', dependencies=[Security(get_api_key)])
async def post(item: ItemGoogleMaps):
    data = item.dict()
    text = data['text'].lower().replace(' помещение ', " пом ").replace(' пом ', " кв ").replace(' кв ', " кВ ")
    from_cadastral = data['from_cadastral']
    for word in config.street_types:
        text = text.replace(word, "")
    response = config.map_client.geocode(text, language='ru')
    pprint(response)
    street = None
    house = None
    town = None
    country = None
    appartment = None
    region = None
    house_internal_building = "Не указан"
    house_internal_number = "Не указан"
    house_internal_letter = "Не указан"
    administrative_area_level_1 = None
    administrative_area_level_2 = None
    if len(response) != 0:
        for element in response[0]['address_components']:
            if 'country' in element['types'] and country is None:
                country = translit(element['long_name'], "ru")
            if 'administrative_area_level_1' in element['types'] and administrative_area_level_1 is None:
                administrative_area_level_1 = translit(element['long_name'], "ru")
            if 'administrative_area_level_2' in element['types'] and administrative_area_level_2 is None:
                administrative_area_level_2 = translit(element['long_name'], "ru")
            if 'locality' in element['types'] and town is None:
                town = translit(element['long_name'], "ru")
            if 'route' in element['types'] and street is None:
                street = translit(element['long_name'], "ru")
            if 'street_number' in element['types'] and house is None:
                house_ = translit(element['long_name'].lower(), "ru").replace('к.`', "корп").split(" ", 1)
                house = re.sub(r'[^\w]$', '', house_[0])
                if len(house_) > 1:
                    if "корп" in house_[1]:
                        house_internal_number = re.sub(r'[^\w]$', '', house_[1].split()[1])
                    if "лит" in house_[1]:
                        house_internal_letter = re.sub(r'[^\w]$', '', house_[1].split()[1])
                    if "строен" in house_[1]:
                        house_internal_building = re.sub(r'[^\w]$', '', house_[1].split()[1])
            if 'subpremise' in element['types'] and appartment is None:
                appartment_ = translit(element['long_name'], "ru")
                if appartment_.isdigit() or appartment_.replace('-', " ").lower().split()[-1] == 'н':
                    appartment = re.sub(r'[^\w]$', '', appartment_).replace(' ', '-')
                else:
                    appartment_ = translit(element['long_name'].lower().replace('к.', "корп"), "ru").split()
                    for id_elem in range(len(appartment_)):
                        if "корп" in appartment_[id_elem] and id_elem + 1 < len(appartment_):
                            house_internal_number = re.sub(r'[^\w]$', '', appartment_[id_elem + 1])
                        if "лит" in appartment_[id_elem] and id_elem + 1 < len(appartment_):
                            house_internal_letter = re.sub(r'[^\w]$', '', appartment_[id_elem + 1])
                        if "строен" in appartment_[id_elem] and id_elem + 1 < len(appartment_):
                            house_internal_building = re.sub(r'[^\w]$', '', appartment_[id_elem + 1])
                        if "кв" in appartment_[id_elem] and id_elem + 1 < len(appartment_):
                            appartment = re.sub(r'[^\w]$', '', appartment_[id_elem + 1])

        formatted_address = translit(response[0]["formatted_address"], "ru")

        if street is None or not has_cyrillic(street):
            raise HTTPException(status_code=406, detail="Address should be made only with russian letters")

        if administrative_area_level_1 is not None and administrative_area_level_1.lower() in config.towns:
            region = config.regions[config.towns.index(administrative_area_level_1.lower())]
            if administrative_area_level_2 is not None:
                town = administrative_area_level_2.split()[0]

        elif town is not None and town.lower() in config.towns:
            region = None
        elif administrative_area_level_1 is not None:
            all_regions = list(config.regions_for_cadastral.values())
            for region_ in all_regions:
                if region_ in administrative_area_level_1:
                    region = region_.replace('a', 'а').replace('A', 'А')
                    break
                if administrative_area_level_1 == 'Ханты-Мансийский автономный округ':
                    region = 'Ханты-Мансийский АО'
                    break
            if region is None:
                raise HTTPException(status_code=400, detail="Region not found")

        if 'линия' in street.lower():
            raise HTTPException(status_code=400, detail="'Линия' is not supported")

        if (town is not None and house is not None) or (from_cadastral and town is not None):
            return dict(country=country,
                        region=region,
                        town=town,
                        street=street,
                        house=house, appartment=appartment,
                        formatted_address=formatted_address,
                        house_internal_letter=house_internal_letter,
                        house_internal_number=house_internal_number,
                        house_internal_building=house_internal_building)
    raise HTTPException(status_code=404, detail="Address not found")


if __name__ == "__main__":
    loop_main = asyncio.new_event_loop()
    config_server = Config(app=app, loop=loop_main, host='localhost', port=3000)
    server = Server(config_server)
    loop_main.run_until_complete(server.serve())
