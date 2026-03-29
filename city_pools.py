"""City pools for each language — used to randomly select a city background per post"""

EN_CITIES = [
    "New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
    "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose",
    "Austin", "Jacksonville", "Fort Worth", "Columbus", "Charlotte",
    "Indianapolis", "San Francisco", "Seattle", "Denver", "Nashville",
    "Oklahoma City", "El Paso", "Washington DC", "Las Vegas", "Louisville",
    "Memphis", "Portland", "Baltimore", "Milwaukee", "Albuquerque",
    "Tucson", "Fresno", "Sacramento", "Omaha", "Colorado Springs",
    "Raleigh", "Miami", "Atlanta", "Minneapolis", "New Orleans",
    "Tampa", "Orlando", "Pittsburgh", "Cincinnati", "St. Louis",
    "Cleveland", "Honolulu", "Anchorage", "Boise", "Richmond",
    "Salt Lake City", "Hartford", "Buffalo", "Providence", "Birmingham",
    "Rochester", "Spokane", "Tacoma", "Bakersfield", "Riverside", "Anaheim",
]

ZH_CITIES = [
    "Shanghai", "Beijing", "Guangzhou", "Shenzhen", "Chengdu",
    "Tianjin", "Chongqing", "Wuhan", "Xian", "Hangzhou",
    "Nanjing", "Suzhou", "Qingdao", "Zhengzhou", "Dongguan",
    "Shenyang", "Foshan", "Harbin", "Dalian", "Changsha",
    "Kunming", "Jinan", "Hefei", "Xiamen", "Taiyuan",
    "Nanchang", "Changchun", "Guiyang", "Wenzhou", "Shijiazhuang",
    "Urumqi", "Nanning", "Lanzhou", "Ningbo", "Fuzhou",
    "Zhongshan", "Luoyang", "Wuxi", "Zhuhai", "Yantai",
    "Haikou", "Liuzhou", "Tangshan", "Xuzhou", "Nantong",
    "Quanzhou", "Huizhou", "Baotou", "Linyi", "Jilin",
]

JA_CITIES = [
    "Tokyo", "Osaka", "Nagoya", "Sapporo", "Fukuoka",
    "Kobe", "Kawasaki", "Kyoto", "Saitama", "Hiroshima",
    "Sendai", "Yokohama", "Chiba", "Kumamoto", "Okayama",
    "Hamamatsu", "Niigata", "Shizuoka", "Hakodate", "Matsuyama",
    "Nagasaki", "Kanazawa", "Oita", "Naha", "Kagoshima",
    "Utsunomiya", "Funabashi", "Hachioji", "Nara", "Wakayama",
    "Toyama", "Gifu", "Aomori", "Morioka", "Akita",
    "Yamagata", "Fukushima", "Mito", "Maebashi", "Kofu",
    "Nagano", "Toyohashi", "Himeji", "Matsumoto", "Kurashiki",
    "Takamatsu", "Kochi", "Miyazaki", "Saga", "Tottori",
]

SLOT_KEYWORDS = {
    "morning": "sunrise",
    "lunch": "street daytime",
    "evening": "night lights",
}

LANG_CITIES = {
    "en": EN_CITIES,
    "zh": ZH_CITIES,
    "ja": JA_CITIES,
}
