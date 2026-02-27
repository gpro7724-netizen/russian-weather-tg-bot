# Список городов РФ 500 тыс.+ для скриптов загрузки фото.
# Используется скриптами download_historic_photos.py и download_landmarks.py.

from dataclasses import dataclass
from typing import Dict


@dataclass
class City:
    slug: str
    name_ru: str
    name_en: str


CITIES: Dict[str, City] = {
    "moscow": City("moscow", "Москва", "Moscow"),
    "spb": City("spb", "Санкт-Петербург", "Saint Petersburg"),
    "novosibirsk": City("novosibirsk", "Новосибирск", "Novosibirsk"),
    "yekaterinburg": City("yekaterinburg", "Екатеринбург", "Yekaterinburg"),
    "kazan": City("kazan", "Казань", "Kazan"),
    "krasnoyarsk": City("krasnoyarsk", "Красноярск", "Krasnoyarsk"),
    "nizhny_novgorod": City("nizhny_novgorod", "Нижний Новгород", "Nizhny Novgorod"),
    "chelyabinsk": City("chelyabinsk", "Челябинск", "Chelyabinsk"),
    "ufa": City("ufa", "Уфа", "Ufa"),
    "krasnodar": City("krasnodar", "Краснодар", "Krasnodar"),
    "samara": City("samara", "Самара", "Samara"),
    "rostov_on_don": City("rostov_on_don", "Ростов-на-Дону", "Rostov-on-Don"),
    "omsk": City("omsk", "Омск", "Omsk"),
    "voronezh": City("voronezh", "Воронеж", "Voronezh"),
    "perm": City("perm", "Пермь", "Perm"),
    "volgograd": City("volgograd", "Волгоград", "Volgograd"),
    "saratov": City("saratov", "Саратов", "Saratov"),
    "tyumen": City("tyumen", "Тюмень", "Tyumen"),
    "tolyatti": City("tolyatti", "Тольятти", "Tolyatti"),
    "mahachkala": City("mahachkala", "Махачкала", "Makhachkala"),
    "barnaul": City("barnaul", "Барнаул", "Barnaul"),
    "izhevsk": City("izhevsk", "Ижевск", "Izhevsk"),
    "khabarovsk": City("khabarovsk", "Хабаровск", "Khabarovsk"),
    "ulyanovsk": City("ulyanovsk", "Ульяновск", "Ulyanovsk"),
    "irkutsk": City("irkutsk", "Иркутск", "Irkutsk"),
    "vladivostok": City("vladivostok", "Владивосток", "Vladivostok"),
    "yaroslavl": City("yaroslavl", "Ярославль", "Yaroslavl"),
    "stavropol": City("stavropol", "Ставрополь", "Stavropol"),
    "sevastopol": City("sevastopol", "Севастополь", "Sevastopol"),
    "naberezhnye_chelny": City("naberezhnye_chelny", "Набережные Челны", "Naberezhnye Chelny"),
    "tomsk": City("tomsk", "Томск", "Tomsk"),
    "balashikha": City("balashikha", "Балашиха", "Balashikha"),
    "kemerovo": City("kemerovo", "Кемерово", "Kemerovo"),
    "orenburg": City("orenburg", "Оренбург", "Orenburg"),
    "novokuznetsk": City("novokuznetsk", "Новокузнецк", "Novokuznetsk"),
    "ryazan": City("ryazan", "Рязань", "Ryazan"),
}
