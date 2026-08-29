"""Build places_aliases.json from the curated seed below.

Coordinates are NOT hand-typed. Each entry's canonical English name is resolved
through OneMap's public (unauthenticated) search, so a mistyped digit cannot
quietly route a passenger to the wrong side of the island. Entries that fail to
resolve are reported and left out rather than guessed at.

    python tools/build_place_aliases.py            # resolve and write
    python tools/build_place_aliases.py --check    # resolve, report, write nothing

Re-run when the seed changes. The output file is committed.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT = BASE_DIR / "places_aliases.json"
ONEMAP_SEARCH = "https://www.onemap.gov.sg/api/common/elastic/search"

SG_LAT = (1.15, 1.48)
SG_LON = (103.6, 104.1)

# (id, name_en, name_zh, category, search_term_or_None, [aliases])
# search_term overrides name_en when OneMap knows the place by another name.
SEED = [
    # ─── Changi Airport ───────────────────────────────────────────────────
    ("changi-airport", "Changi Airport", "樟宜机场", "airport", "Changi Airport Terminal 2",
     ["changi airport", "changi", "airport", "樟宜机场", "机场", "changi apt"]),
    ("changi-airport-t1", "Changi Airport Terminal 1", "樟宜机场 1 号航站楼", "airport", None,
     ["changi airport t1", "airport t1", "terminal 1", "t1", "樟宜机场 t1", "机场 t1", "一号航站楼"]),
    ("changi-airport-t2", "Changi Airport Terminal 2", "樟宜机场 2 号航站楼", "airport", None,
     ["changi airport t2", "airport t2", "terminal 2", "t2", "樟宜机场 t2", "机场 t2", "二号航站楼"]),
    ("changi-airport-t3", "Changi Airport Terminal 3", "樟宜机场 3 号航站楼", "airport", None,
     ["changi airport t3", "airport t3", "terminal 3", "t3", "樟宜机场 t3", "机场 t3", "三号航站楼"]),
    ("changi-airport-t4", "Changi Airport Terminal 4", "樟宜机场 4 号航站楼", "airport", None,
     ["changi airport t4", "airport t4", "terminal 4", "t4", "樟宜机场 t4", "机场 t4", "四号航站楼"]),
    ("jewel-changi", "Jewel Changi Airport", "星耀樟宜", "mall", None,
     ["jewel", "jewel changi", "星耀樟宜", "星耀"]),
    ("changi-airport-mrt", "Changi Airport MRT Station", "樟宜机场地铁站", "mrt", None,
     ["changi airport mrt", "changi airport station", "樟宜机场地铁站"]),

    # ─── Public hospitals ─────────────────────────────────────────────────
    ("changi-general-hospital", "Changi General Hospital", "樟宜综合医院", "hospital", None,
     ["cgh", "changi general hospital", "changi hospital", "樟宜综合医院", "樟宜医院"]),
    ("singapore-general-hospital", "Singapore General Hospital", "新加坡中央医院", "hospital", None,
     ["sgh", "singapore general hospital", "新加坡中央医院", "中央医院"]),
    ("tan-tock-seng-hospital", "Tan Tock Seng Hospital", "陈笃生医院", "hospital", None,
     ["ttsh", "tan tock seng", "tan tock seng hospital", "陈笃生医院", "陈笃生"]),
    ("national-university-hospital", "National University Hospital", "国立大学医院", "hospital", None,
     ["nuh", "national university hospital", "国立大学医院"]),
    ("kk-womens-and-childrens-hospital", "KK Women's and Children's Hospital", "竹脚妇幼医院", "hospital", None,
     ["kkh", "kk hospital", "kk women's and children's hospital", "竹脚妇幼医院", "竹脚医院"]),
    ("khoo-teck-puat-hospital", "Khoo Teck Puat Hospital", "邱德拔医院", "hospital", None,
     ["ktph", "khoo teck puat", "khoo teck puat hospital", "邱德拔医院"]),
    ("ng-teng-fong-general-hospital", "Ng Teng Fong General Hospital", "黄廷方综合医院", "hospital", None,
     ["ntfgh", "ng teng fong", "ng teng fong general hospital", "黄廷方综合医院"]),
    ("sengkang-general-hospital", "Sengkang General Hospital", "盛港综合医院", "hospital", None,
     ["skh", "sengkang general hospital", "sengkang hospital", "盛港综合医院", "盛港医院"]),
    ("institute-of-mental-health", "Institute of Mental Health", "心理卫生学院", "hospital", None,
     ["imh", "institute of mental health", "心理卫生学院"]),
    ("national-heart-centre", "National Heart Centre Singapore", "国家心脏中心", "hospital", None,
     ["nhcs", "national heart centre", "国家心脏中心"]),
    ("national-cancer-centre", "National Cancer Centre Singapore", "国家癌症中心", "hospital", None,
     ["nccs", "national cancer centre", "国家癌症中心"]),
    ("mount-elizabeth-hospital", "Mount Elizabeth Hospital", "伊丽莎白医院", "hospital", None,
     ["mount elizabeth", "mt elizabeth", "伊丽莎白医院"]),
    ("gleneagles-hospital", "Gleneagles Hospital", "鹰阁医院", "hospital", None,
     ["gleneagles", "鹰阁医院"]),
    ("raffles-hospital", "Raffles Hospital", "莱佛士医院", "hospital", None,
     ["raffles hospital", "莱佛士医院"]),
    ("mount-alvernia-hospital", "Mount Alvernia Hospital", "安微尼亚山医院", "hospital", None,
     ["mount alvernia", "mt alvernia", "安微尼亚山医院"]),
    ("parkway-east-hospital", "Parkway East Hospital", "百汇东岸医院", "hospital", None,
     ["parkway east", "parkway east hospital", "百汇东岸医院"]),
    ("woodlands-health-campus", "Woodlands Health Campus", "兀兰健康园区", "hospital", None,
     ["woodlands health", "woodlands health campus", "兀兰健康园区"]),
    ("alexandra-hospital", "Alexandra Hospital", "亚历山大医院", "hospital", None,
     ["alexandra hospital", "亚历山大医院"]),

    # ─── Polyclinics ──────────────────────────────────────────────────────
    ("pasir-ris-polyclinic", "Pasir Ris Polyclinic", "巴西立综合诊疗所", "clinic", None,
     ["pasir ris polyclinic", "pasir ris poly", "巴西立综合诊疗所", "巴西立诊所"]),
    ("tampines-polyclinic", "Tampines Polyclinic", "淡滨尼综合诊疗所", "clinic", None,
     ["tampines polyclinic", "tampines poly", "淡滨尼综合诊疗所"]),
    ("bedok-polyclinic", "Bedok Polyclinic", "勿洛综合诊疗所", "clinic", None,
     ["bedok polyclinic", "bedok poly", "勿洛综合诊疗所"]),
    ("geylang-polyclinic", "Geylang Polyclinic", "芽笼综合诊疗所", "clinic", None,
     ["geylang polyclinic", "geylang poly", "芽笼综合诊疗所"]),
    ("toa-payoh-polyclinic", "Toa Payoh Polyclinic", "大巴窑综合诊疗所", "clinic", None,
     ["toa payoh polyclinic", "toa payoh poly", "大巴窑综合诊疗所"]),
    ("ang-mo-kio-polyclinic", "Ang Mo Kio Polyclinic", "宏茂桥综合诊疗所", "clinic", None,
     ["ang mo kio polyclinic", "amk polyclinic", "amk poly", "宏茂桥综合诊疗所"]),
    ("sengkang-polyclinic", "Sengkang Polyclinic", "盛港综合诊疗所", "clinic", None,
     ["sengkang polyclinic", "sengkang poly", "盛港综合诊疗所"]),
    ("punggol-polyclinic", "Punggol Polyclinic", "榜鹅综合诊疗所", "clinic", None,
     ["punggol polyclinic", "punggol poly", "榜鹅综合诊疗所"]),

    # ─── Malls: east ──────────────────────────────────────────────────────
    ("white-sands", "White Sands", "白沙购物中心", "mall", None,
     ["white sands", "whitesands", "白沙购物广场", "白沙购物中心", "白沙"]),
    ("downtown-east", "Downtown East", "东部市中心", "mall", None,
     ["downtown east", "d'resort", "东部市中心"]),
    ("tampines-mall", "Tampines Mall", "淡滨尼购物中心", "mall", None,
     ["tampines mall", "淡滨尼购物中心"]),
    ("tampines-one", "Tampines 1", "淡滨尼一号", "mall", None,
     ["tampines 1", "tampines one", "淡滨尼一号"]),
    ("century-square", "Century Square", "世纪广场", "mall", None,
     ["century square", "世纪广场"]),
    ("our-tampines-hub", "Our Tampines Hub", "我们的淡滨尼", "government", None,
     ["our tampines hub", "oth", "tampines hub", "我们的淡滨尼"]),
    ("bedok-mall", "Bedok Mall", "勿洛坊", "mall", None,
     ["bedok mall", "勿洛坊"]),
    ("changi-city-point", "Changi City Point", "樟宜城市坊", "mall", None,
     ["changi city point", "樟宜城市坊"]),
    ("parkway-parade", "Parkway Parade", "百汇广场", "mall", None,
     ["parkway parade", "百汇广场"]),
    ("katong-square", "Katong Square", "加东广场", "mall", None,
     ["katong square", "加东广场"]),
    ("eastpoint-mall", "Eastpoint Mall", "东点城", "mall", None,
     ["eastpoint mall", "eastpoint", "东点城"]),
    ("loyang-point", "Loyang Point", "罗央坊", "mall", None,
     ["loyang point", "罗央坊"]),

    # ─── Malls: island-wide ───────────────────────────────────────────────
    ("vivocity", "VivoCity", "怡丰城", "mall", None,
     ["vivocity", "vivo city", "怡丰城"]),
    ("ion-orchard", "ION Orchard", "爱雍乌节", "mall", None,
     ["ion orchard", "ion", "爱雍乌节"]),
    ("ngee-ann-city", "Ngee Ann City", "义安城", "mall", None,
     ["ngee ann city", "takashimaya", "taka", "义安城", "高岛屋"]),
    ("plaza-singapura", "Plaza Singapura", "狮城大厦", "mall", None,
     ["plaza singapura", "狮城大厦"]),
    ("bugis-junction", "Bugis Junction", "白沙浮广场", "mall", None,
     ["bugis junction", "白沙浮广场"]),
    ("bugis-plus", "Bugis+", "白沙浮商业城", "mall", None,
     ["bugis plus", "bugis+", "白沙浮商业城"]),
    ("suntec-city", "Suntec City", "新达城", "mall", None,
     ["suntec city", "suntec", "新达城"]),
    ("marina-bay-sands", "Marina Bay Sands", "滨海湾金沙", "landmark", None,
     ["marina bay sands", "mbs", "滨海湾金沙", "金沙"]),
    ("northpoint-city", "Northpoint City", "纳福城", "mall", None,
     ["northpoint city", "northpoint", "纳福城"]),
    ("causeway-point", "Causeway Point", "长堤坊", "mall", None,
     ["causeway point", "长堤坊"]),
    ("jurong-point", "Jurong Point", "裕廊坊", "mall", None,
     ["jurong point", "裕廊坊"]),
    ("westgate", "Westgate", "西城", "mall", None,
     ["westgate", "西城"]),
    ("jem", "JEM", "裕廊 JEM", "mall", None,
     ["jem"]),
    ("nex", "NEX", "纳福", "mall", None,
     ["nex", "nex mall"]),
    ("amk-hub", "AMK Hub", "宏茂桥中心", "mall", None,
     ["amk hub", "ang mo kio hub", "宏茂桥中心"]),
    ("compass-one", "Compass One", "康埔桦一号", "mall", None,
     ["compass one", "compass point", "康埔桦一号"]),
    ("waterway-point", "Waterway Point", "水滨坊", "mall", None,
     ["waterway point", "水滨坊"]),
    ("junction-8", "Junction 8", "碧山第八站", "mall", None,
     ["junction 8", "j8", "碧山第八站"]),
    ("paya-lebar-quarter", "Paya Lebar Quarter", "巴耶利峇广场", "mall", None,
     ["paya lebar quarter", "plq", "巴耶利峇广场"]),
    ("city-square-mall", "City Square Mall", "城市广场", "mall", None,
     ["city square mall", "城市广场"]),
    ("funan", "Funan", "福南", "mall", None,
     ["funan", "funan mall", "福南"]),
    ("raffles-city", "Raffles City", "莱佛士城", "mall", None,
     ["raffles city", "莱佛士城"]),
    ("great-world", "Great World", "大世界", "mall", None,
     ["great world", "great world city", "大世界"]),
    ("313-somerset", "313@Somerset", "索美塞 313", "mall", None,
     ["313 somerset", "313@somerset", "313", "索美塞313"]),
    ("mustafa-centre", "Mustafa Centre", "慕斯达法中心", "mall", None,
     ["mustafa", "mustafa centre", "慕斯达法中心"]),
    ("lucky-plaza", "Lucky Plaza", "幸运商业中心", "mall", None,
     ["lucky plaza", "幸运商业中心"]),
    ("tiong-bahru-plaza", "Tiong Bahru Plaza", "中峇鲁广场", "mall", None,
     ["tiong bahru plaza", "中峇鲁广场"]),
    ("hougang-mall", "Hougang Mall", "后港坊", "mall", None,
     ["hougang mall", "后港坊"]),
    ("clementi-mall", "The Clementi Mall", "金文泰坊", "mall", None,
     ["clementi mall", "金文泰坊"]),
    ("imm", "IMM", "怡满", "mall", None,
     ["imm", "imm building"]),
    ("bukit-panjang-plaza", "Bukit Panjang Plaza", "武吉班让广场", "mall", None,
     ["bukit panjang plaza", "bp plaza", "武吉班让广场"]),
    ("lot-one", "Lot One", "第一乐广场", "mall", None,
     ["lot one", "lot 1", "第一乐广场"]),
    ("west-mall", "West Mall", "西坊", "mall", None,
     ["west mall", "西坊"]),
    ("seletar-mall", "The Seletar Mall", "实里达坊", "mall", None,
     ["seletar mall", "实里达坊"]),
    ("heartland-mall", "Heartland Mall", "心乐坊", "mall", None,
     ["heartland mall", "kovan mall", "心乐坊"]),

    # ─── MRT: east ────────────────────────────────────────────────────────
    ("pasir-ris-mrt", "Pasir Ris MRT Station", "巴西立地铁站", "mrt", None,
     ["pasir ris mrt", "pasir ris station", "巴西立地铁站", "巴西立站"]),
    ("tampines-mrt", "Tampines MRT Station", "淡滨尼地铁站", "mrt", None,
     ["tampines mrt", "tampines station", "淡滨尼地铁站"]),
    ("simei-mrt", "Simei MRT Station", "四美地铁站", "mrt", None,
     ["simei mrt", "simei station", "四美地铁站"]),
    ("tanah-merah-mrt", "Tanah Merah MRT Station", "丹那美拉地铁站", "mrt", None,
     ["tanah merah mrt", "tanah merah", "丹那美拉地铁站"]),
    ("bedok-mrt", "Bedok MRT Station", "勿洛地铁站", "mrt", None,
     ["bedok mrt", "bedok station", "勿洛地铁站"]),
    ("expo-mrt", "Expo MRT Station", "博览地铁站", "mrt", None,
     ["expo mrt", "expo station", "博览地铁站"]),
    ("eunos-mrt", "Eunos MRT Station", "友诺士地铁站", "mrt", None,
     ["eunos mrt", "eunos", "友诺士地铁站"]),
    ("kembangan-mrt", "Kembangan MRT Station", "景万岸地铁站", "mrt", None,
     ["kembangan mrt", "kembangan", "景万岸地铁站"]),
    ("paya-lebar-mrt", "Paya Lebar MRT Station", "巴耶利峇地铁站", "mrt", None,
     ["paya lebar mrt", "paya lebar station", "巴耶利峇地铁站"]),
    ("aljunied-mrt", "Aljunied MRT Station", "阿裕尼地铁站", "mrt", None,
     ["aljunied mrt", "aljunied", "阿裕尼地铁站"]),

    # ─── MRT: central and interchanges ────────────────────────────────────
    ("city-hall-mrt", "City Hall MRT Station", "政府大厦地铁站", "mrt", None,
     ["city hall mrt", "city hall station", "政府大厦地铁站"]),
    ("raffles-place-mrt", "Raffles Place MRT Station", "莱佛士坊地铁站", "mrt", None,
     ["raffles place mrt", "raffles place station", "莱佛士坊地铁站"]),
    ("dhoby-ghaut-mrt", "Dhoby Ghaut MRT Station", "多美歌地铁站", "mrt", None,
     ["dhoby ghaut mrt", "dhoby ghaut", "多美歌地铁站"]),
    ("orchard-mrt", "Orchard MRT Station", "乌节地铁站", "mrt", None,
     ["orchard mrt", "orchard station", "乌节地铁站"]),
    ("somerset-mrt", "Somerset MRT Station", "索美塞地铁站", "mrt", None,
     ["somerset mrt", "somerset", "索美塞地铁站"]),
    ("newton-mrt", "Newton MRT Station", "纽顿地铁站", "mrt", None,
     ["newton mrt", "newton station", "纽顿地铁站"]),
    ("bugis-mrt", "Bugis MRT Station", "武吉士地铁站", "mrt", None,
     ["bugis mrt", "bugis station", "武吉士地铁站"]),
    ("outram-park-mrt", "Outram Park MRT Station", "欧南园地铁站", "mrt", None,
     ["outram park mrt", "outram park", "欧南园地铁站"]),
    ("tanjong-pagar-mrt", "Tanjong Pagar MRT Station", "丹戎巴葛地铁站", "mrt", None,
     ["tanjong pagar mrt", "tanjong pagar", "丹戎巴葛地铁站"]),
    ("marina-bay-mrt", "Marina Bay MRT Station", "滨海湾地铁站", "mrt", None,
     ["marina bay mrt", "marina bay station", "滨海湾地铁站"]),
    ("harbourfront-mrt", "HarbourFront MRT Station", "港湾地铁站", "mrt", None,
     ["harbourfront mrt", "harbourfront", "港湾地铁站"]),
    ("jurong-east-mrt", "Jurong East MRT Station", "裕廊东地铁站", "mrt", None,
     ["jurong east mrt", "jurong east station", "裕廊东地铁站"]),
    ("woodlands-mrt", "Woodlands MRT Station", "兀兰地铁站", "mrt", None,
     ["woodlands mrt", "woodlands station", "兀兰地铁站"]),
    ("yishun-mrt", "Yishun MRT Station", "义顺地铁站", "mrt", None,
     ["yishun mrt", "yishun station", "义顺地铁站"]),
    ("ang-mo-kio-mrt", "Ang Mo Kio MRT Station", "宏茂桥地铁站", "mrt", None,
     ["ang mo kio mrt", "amk mrt", "amk station", "宏茂桥地铁站"]),
    ("bishan-mrt", "Bishan MRT Station", "碧山地铁站", "mrt", None,
     ["bishan mrt", "bishan station", "碧山地铁站"]),
    ("serangoon-mrt", "Serangoon MRT Station", "实龙岗地铁站", "mrt", None,
     ["serangoon mrt", "serangoon station", "实龙岗地铁站"]),
    ("hougang-mrt", "Hougang MRT Station", "后港地铁站", "mrt", None,
     ["hougang mrt", "hougang station", "后港地铁站"]),
    ("sengkang-mrt", "Sengkang MRT Station", "盛港地铁站", "mrt", None,
     ["sengkang mrt", "sengkang station", "盛港地铁站"]),
    ("punggol-mrt", "Punggol MRT Station", "榜鹅地铁站", "mrt", None,
     ["punggol mrt", "punggol station", "榜鹅地铁站"]),
    ("toa-payoh-mrt", "Toa Payoh MRT Station", "大巴窑地铁站", "mrt", None,
     ["toa payoh mrt", "toa payoh station", "大巴窑地铁站"]),
    ("novena-mrt", "Novena MRT Station", "诺维娜地铁站", "mrt", None,
     ["novena mrt", "novena", "诺维娜地铁站"]),
    ("little-india-mrt", "Little India MRT Station", "小印度地铁站", "mrt", None,
     ["little india mrt", "little india station", "小印度地铁站"]),
    ("clementi-mrt", "Clementi MRT Station", "金文泰地铁站", "mrt", None,
     ["clementi mrt", "clementi station", "金文泰地铁站"]),
    ("buona-vista-mrt", "Buona Vista MRT Station", "波那维斯达地铁站", "mrt", None,
     ["buona vista mrt", "buona vista", "波那维斯达地铁站"]),
    ("boon-lay-mrt", "Boon Lay MRT Station", "文礼地铁站", "mrt", None,
     ["boon lay mrt", "boon lay station", "文礼地铁站"]),
    ("choa-chu-kang-mrt", "Choa Chu Kang MRT Station", "蔡厝港地铁站", "mrt", None,
     ["choa chu kang mrt", "cck mrt", "cck station", "蔡厝港地铁站"]),
    ("bukit-batok-mrt", "Bukit Batok MRT Station", "武吉巴督地铁站", "mrt", None,
     ["bukit batok mrt", "bukit batok station", "武吉巴督地铁站"]),
    ("canberra-mrt", "Canberra MRT Station", "坎贝拉地铁站", "mrt", None,
     ["canberra", "canberra mrt", "canberra station", "坎贝拉地铁站"]),
    ("kallang-mrt", "Kallang MRT Station", "加冷地铁站", "mrt", None,
     ["kallang mrt", "kallang station", "加冷地铁站"]),
    ("lavender-mrt", "Lavender MRT Station", "劳明达地铁站", "mrt", None,
     ["lavender mrt", "lavender", "劳明达地铁站"]),
    ("tai-seng-mrt", "Tai Seng MRT Station", "大成地铁站", "mrt", None,
     ["tai seng mrt", "tai seng", "大成地铁站"]),
    ("kovan-mrt", "Kovan MRT Station", "高文地铁站", "mrt", None,
     ["kovan mrt", "kovan station", "高文地铁站"]),
    ("botanic-gardens-mrt", "Botanic Gardens MRT Station", "植物园地铁站", "mrt", None,
     ["botanic gardens mrt", "botanic gardens station", "植物园地铁站"]),
    ("caldecott-mrt", "Caldecott MRT Station", "加利谷地铁站", "mrt", None,
     ["caldecott mrt", "caldecott", "加利谷地铁站"]),
    ("marymount-mrt", "Marymount MRT Station", "玛丽蒙地铁站", "mrt", None,
     ["marymount mrt", "marymount", "玛丽蒙地铁站"]),
    ("braddell-mrt", "Braddell MRT Station", "布莱德地铁站", "mrt", None,
     ["braddell mrt", "braddell", "布莱德地铁站"]),
    ("queenstown-mrt", "Queenstown MRT Station", "女皇镇地铁站", "mrt", None,
     ["queenstown mrt", "queenstown", "女皇镇地铁站"]),
    ("redhill-mrt", "Redhill MRT Station", "红山地铁站", "mrt", None,
     ["redhill mrt", "redhill", "红山地铁站"]),
    ("commonwealth-mrt", "Commonwealth MRT Station", "联邦地铁站", "mrt", None,
     ["commonwealth mrt", "commonwealth", "联邦地铁站"]),
    ("farrer-park-mrt", "Farrer Park MRT Station", "花拉公园地铁站", "mrt", None,
     ["farrer park mrt", "farrer park", "花拉公园地铁站"]),
    ("boon-keng-mrt", "Boon Keng MRT Station", "文庆地铁站", "mrt", None,
     ["boon keng mrt", "boon keng", "文庆地铁站"]),
    ("potong-pasir-mrt", "Potong Pasir MRT Station", "波东巴西地铁站", "mrt", None,
     ["potong pasir mrt", "potong pasir", "波东巴西地铁站"]),
    ("buangkok-mrt", "Buangkok MRT Station", "万国地铁站", "mrt", None,
     ["buangkok mrt", "buangkok", "万国地铁站"]),

    # ─── Bus interchanges ─────────────────────────────────────────────────
    ("pasir-ris-bus-interchange", "Pasir Ris Bus Interchange", "巴西立巴士转换站", "interchange", "Pasir Ris Int",
     ["pasir ris bus interchange", "pasir ris interchange", "巴西立巴士转换站", "巴西立车站"]),
    ("tampines-bus-interchange", "Tampines Bus Interchange", "淡滨尼巴士转换站", "interchange", None,
     ["tampines bus interchange", "tampines interchange", "淡滨尼巴士转换站"]),
    ("bedok-bus-interchange", "Bedok Bus Interchange", "勿洛巴士转换站", "interchange", "Bedok Int",
     ["bedok bus interchange", "bedok interchange", "勿洛巴士转换站"]),
    ("sengkang-bus-interchange", "Sengkang Bus Interchange", "盛港巴士转换站", "interchange", None,
     ["sengkang bus interchange", "sengkang interchange", "盛港巴士转换站"]),
    ("punggol-bus-interchange", "Punggol Bus Interchange", "榜鹅巴士转换站", "interchange", None,
     ["punggol bus interchange", "punggol interchange", "榜鹅巴士转换站"]),
    ("hougang-bus-interchange", "Hougang Central Bus Interchange", "后港巴士转换站", "interchange", None,
     ["hougang bus interchange", "hougang interchange", "后港巴士转换站"]),
    ("serangoon-bus-interchange", "Serangoon Bus Interchange", "实龙岗巴士转换站", "interchange", None,
     ["serangoon bus interchange", "serangoon interchange", "实龙岗巴士转换站"]),
    ("ang-mo-kio-bus-interchange", "Ang Mo Kio Bus Interchange", "宏茂桥巴士转换站", "interchange", None,
     ["ang mo kio bus interchange", "amk bus interchange", "amk interchange", "宏茂桥巴士转换站"]),
    ("toa-payoh-bus-interchange", "Toa Payoh Bus Interchange", "大巴窑巴士转换站", "interchange", None,
     ["toa payoh bus interchange", "toa payoh interchange", "大巴窑巴士转换站"]),
    ("jurong-east-bus-interchange", "Jurong East Bus Interchange", "裕廊东巴士转换站", "interchange", None,
     ["jurong east bus interchange", "jurong east interchange", "裕廊东巴士转换站"]),
    ("woodlands-bus-interchange", "Woodlands Bus Interchange", "兀兰巴士转换站", "interchange", None,
     ["woodlands bus interchange", "woodlands interchange", "兀兰巴士转换站"]),
    ("yishun-bus-interchange", "Yishun Bus Interchange", "义顺巴士转换站", "interchange", None,
     ["yishun bus interchange", "yishun interchange", "义顺巴士转换站"]),
    ("boon-lay-bus-interchange", "Boon Lay Bus Interchange", "文礼巴士转换站", "interchange", None,
     ["boon lay bus interchange", "boon lay interchange", "文礼巴士转换站"]),
    ("choa-chu-kang-bus-interchange", "Choa Chu Kang Bus Interchange", "蔡厝港巴士转换站", "interchange", None,
     ["choa chu kang bus interchange", "cck bus interchange", "cck interchange", "蔡厝港巴士转换站"]),
    ("clementi-bus-interchange", "Clementi Bus Interchange", "金文泰巴士转换站", "interchange", None,
     ["clementi bus interchange", "clementi interchange", "金文泰巴士转换站"]),
    ("bishan-bus-interchange", "Bishan Bus Interchange", "碧山巴士转换站", "interchange", None,
     ["bishan bus interchange", "bishan interchange", "碧山巴士转换站"]),

    # ─── Government and civic ─────────────────────────────────────────────
    ("ica-building", "ICA Building", "移民与关卡局大厦", "government", "Immigration and Checkpoints Authority",
     ["ica", "ica building", "immigration", "移民与关卡局", "移民厅"]),
    ("hdb-hub", "HDB Hub", "建屋局中心", "government", None,
     ["hdb hub", "hdb", "建屋局中心", "建屋局"]),
    ("cpf-board", "CPF Building", "公积金局大厦", "government", None,
     ["cpf", "cpf board", "cpf building", "公积金局"]),
    ("revenue-house", "Revenue House", "税务大厦", "government", None,
     ["iras", "revenue house", "税务局", "税务大厦"]),
    ("supreme-court", "Supreme Court", "最高法院", "government", None,
     ["supreme court", "最高法院"]),
    ("parliament-house", "Parliament House", "国会大厦", "government", None,
     ["parliament house", "parliament", "国会大厦"]),
    ("national-library", "National Library", "国家图书馆", "government", None,
     ["national library", "国家图书馆"]),
    ("tampines-regional-library", "Tampines Regional Library", "淡滨尼区域图书馆", "government", "Tampines Library",
     ["tampines regional library", "tampines library", "淡滨尼图书馆"]),
    ("pasir-ris-elias-cc", "Pasir Ris Elias Community Club", "巴西立伊莱雅斯民众俱乐部", "government", None,
     ["elias cc", "pasir ris elias community club", "巴西立民众俱乐部", "民众俱乐部"]),
    ("mom-services-centre", "Ministry of Manpower Services Centre", "人力部服务中心", "government", None,
     ["mom", "ministry of manpower", "人力部"]),
    ("singapore-land-authority", "Singapore Land Authority", "新加坡土地管理局", "government", None,
     ["sla", "singapore land authority", "土地管理局"]),

    # ─── Landmarks and attractions ────────────────────────────────────────
    ("gardens-by-the-bay", "Gardens by the Bay", "滨海湾花园", "landmark", None,
     ["gardens by the bay", "滨海湾花园"]),
    ("merlion-park", "Merlion Park", "鱼尾狮公园", "landmark", None,
     ["merlion", "merlion park", "鱼尾狮公园", "鱼尾狮"]),
    ("sentosa", "Sentosa", "圣淘沙", "landmark", None,
     ["sentosa", "圣淘沙"]),
    ("universal-studios", "Universal Studios Singapore", "环球影城", "landmark", None,
     ["universal studios", "uss", "环球影城"]),
    ("singapore-zoo", "Singapore Zoo", "新加坡动物园", "landmark", None,
     ["singapore zoo", "zoo", "新加坡动物园", "动物园"]),
    ("night-safari", "Night Safari", "夜间野生动物园", "landmark", None,
     ["night safari", "夜间野生动物园"]),
    ("bird-paradise", "Bird Paradise", "飞禽公园", "landmark", None,
     ["bird paradise", "bird park", "jurong bird park", "飞禽公园"]),
    ("science-centre", "Science Centre Singapore", "新加坡科学馆", "landmark", None,
     ["science centre", "science center", "新加坡科学馆", "科学馆"]),
    ("esplanade", "Esplanade", "滨海艺术中心", "landmark", None,
     ["esplanade", "滨海艺术中心", "榴莲壳"]),
    ("singapore-flyer", "Singapore Flyer", "新加坡摩天观景轮", "landmark", None,
     ["singapore flyer", "flyer", "摩天观景轮"]),
    ("national-stadium", "National Stadium", "国家体育场", "landmark", None,
     ["national stadium", "sports hub", "国家体育场"]),
    ("botanic-gardens", "Singapore Botanic Gardens", "新加坡植物园", "landmark", None,
     ["botanic gardens", "植物园"]),
    ("east-coast-park", "East Coast Park", "东海岸公园", "landmark", None,
     ["east coast park", "ecp", "东海岸公园"]),
    ("pasir-ris-park", "Pasir Ris Park", "巴西立公园", "landmark", None,
     ["pasir ris park", "巴西立公园"]),
    ("changi-beach-park", "Changi Beach Park", "樟宜海滩公园", "landmark", None,
     ["changi beach", "changi beach park", "樟宜海滩"]),
    ("singapore-expo", "Singapore Expo", "新加坡博览中心", "landmark", None,
     ["singapore expo", "expo", "新加坡博览中心", "博览中心"]),
    ("suntec-convention", "Suntec Singapore Convention Centre", "新达城会展中心", "landmark", None,
     ["suntec convention", "suntec convention centre", "新达城会展中心"]),
    ("chinatown", "Chinatown", "牛车水", "landmark", None,
     ["chinatown", "牛车水"]),
    ("little-india", "Little India", "小印度", "landmark", None,
     ["little india", "小印度"]),
    ("kampong-glam", "Kampong Glam", "甘榜格南", "landmark", None,
     ["kampong glam", "arab street", "甘榜格南", "阿拉伯街"]),
    ("clarke-quay", "Clarke Quay", "克拉码头", "landmark", None,
     ["clarke quay", "克拉码头"]),
    ("boat-quay", "Boat Quay", "驳船码头", "landmark", None,
     ["boat quay", "驳船码头"]),
    ("orchard-road", "Orchard Road", "乌节路", "landmark", None,
     ["orchard road", "orchard", "乌节路"]),
    ("one-raffles-place", "One Raffles Place", "莱佛士坊一号", "landmark", None,
     ["one raffles place", "莱佛士坊一号"]),
    ("marina-barrage", "Marina Barrage", "滨海堤坝", "landmark", None,
     ["marina barrage", "滨海堤坝"]),
    ("fort-canning-park", "Fort Canning Park", "福康宁公园", "landmark", None,
     ["fort canning", "fort canning park", "福康宁公园"]),
    ("bukit-timah-nature-reserve", "Bukit Timah Nature Reserve", "武吉知马自然保护区", "landmark", None,
     ["bukit timah nature reserve", "武吉知马自然保护区"]),
    ("mandai-wildlife-reserve", "Mandai Wildlife Reserve", "万礼野生动物保护区", "landmark", None,
     ["mandai", "mandai wildlife reserve", "万礼"]),
    ("river-wonders", "River Wonders", "河川生态园", "landmark", None,
     ["river wonders", "river safari", "河川生态园"]),

    # ─── Education ────────────────────────────────────────────────────────
    ("nus", "National University of Singapore", "新加坡国立大学", "education", None,
     ["nus", "national university of singapore", "新加坡国立大学", "国大"]),
    ("ntu", "Nanyang Technological University", "南洋理工大学", "education", None,
     ["ntu", "nanyang technological university", "南洋理工大学", "南大"]),
    ("smu", "Singapore Management University", "新加坡管理大学", "education", None,
     ["smu", "singapore management university", "新加坡管理大学"]),
    ("sutd", "Singapore University of Technology and Design", "新加坡科技设计大学", "education", None,
     ["sutd", "singapore university of technology and design", "新加坡科技设计大学"]),
    ("temasek-polytechnic", "Temasek Polytechnic", "淡马锡理工学院", "education", None,
     ["temasek poly", "temasek polytechnic", "tp", "淡马锡理工学院"]),
    ("ngee-ann-polytechnic", "Ngee Ann Polytechnic", "义安理工学院", "education", None,
     ["ngee ann poly", "ngee ann polytechnic", "np", "义安理工学院"]),
    ("singapore-polytechnic", "Singapore Polytechnic", "新加坡理工学院", "education", None,
     ["singapore poly", "singapore polytechnic", "sp", "新加坡理工学院"]),
    ("republic-polytechnic", "Republic Polytechnic", "共和理工学院", "education", None,
     ["republic poly", "republic polytechnic", "rp", "共和理工学院"]),
    ("nanyang-polytechnic", "Nanyang Polytechnic", "南洋理工学院", "education", None,
     ["nanyang poly", "nanyang polytechnic", "nyp", "南洋理工学院"]),
]


def resolve_coordinates(search_term, attempts=4):
    """OneMap's public search throttles a fast loop, returning an empty result
    set rather than an error status. Retry with backoff before believing a miss.
    """
    for attempt in range(attempts):
        try:
            response = requests.get(
                ONEMAP_SEARCH,
                params={
                    "searchVal": search_term,
                    "returnGeom": "Y",
                    "getAddrDetails": "Y",
                    "pageNum": 1,
                },
                timeout=25,
            )
            response.raise_for_status()
            results = response.json().get("results") or []
            if results:
                hit = results[0]
                return float(hit["LATITUDE"]), float(hit["LONGITUDE"])
        except Exception:
            pass
        time.sleep(1.5 * (attempt + 1))
    return None


def inside_singapore(lat, lon):
    return SG_LAT[0] <= lat <= SG_LAT[1] and SG_LON[0] <= lon <= SG_LON[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="resolve and report, write nothing")
    args = parser.parse_args()

    places = []
    failures = []

    for place_id, name_en, name_zh, category, search_term, aliases in SEED:
        term = search_term or name_en
        try:
            coords = resolve_coordinates(term)
        except Exception as exc:
            coords = None
            print(f"  !! {place_id}: {type(exc).__name__}")

        if not coords or not inside_singapore(*coords):
            failures.append((place_id, term, coords))
            print(f"  ?? {place_id}: unresolved via {term!r} (got {coords})")
            continue

        lat, lon = coords
        places.append({
            "id": place_id,
            "name_en": name_en,
            "name_zh": name_zh,
            "category": category,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "aliases": sorted(set(aliases)),
        })
        time.sleep(0.8)  # OneMap search is public and throttles; pace the loop

    print(f"\nresolved {len(places)}/{len(SEED)}; {len(failures)} unresolved")

    if failures:
        print("\nUnresolved (fix the seed's search term, do not guess coordinates):")
        for place_id, term, coords in failures:
            print(f"  {place_id:40} {term!r} -> {coords}")

    if args.check:
        print("\n--check: nothing written")
        return 1 if failures else 0

    OUTPUT.write_text(
        json.dumps({"places": places}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
