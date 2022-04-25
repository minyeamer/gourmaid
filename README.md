# Gourmaid
카카오 API를 통해 수집한 데이터에 기반한 맛집 검색 서비스   
카카오 장소 검색을 맛집에 최적화시키고 웹상에서 구현하여 사용자 편의성 제공

<br>

![search](https://blog.kakaocdn.net/dn/kCP9T/btrArJisEgq/1wKfTFSLyiw93NkE9EiNyK/img.gif)

---

## Index
  1. [How to Use](#1-how-to-use)
  2. [Project Description](#2-project-description)
  3. [Implementation](#3-implementation)
  4. [Main Classes](#4-main-classes)
  5. [Main Methods](#5-main-methods)
  6. [Input/Output](#6-inputoutput)
  7. [Error List](#7-error-list)
  8. [Restropective](#8-restropective)

---

## 1. How to Use
- `streamlit run app.py --server.port 8080` 명령어를 입력하여 실행
- `streamlit` 라이브러리를 통해 로컬 서버에서 웹이 구현되었기에 외부에서 접근은 불가
- 데이터 수집을 위해 카카오 REST API 및 네이버 CLOVA API를 사용하였으며,   
  지도 표시를 위해 카카오 JavaScript API를 추가로 사용
- API 키는 과금 우려로 제외하였으며, 실행 시 해당 부분에 본인 API 키 입력
- 관리자 객체 생성 시 서비스 데이터를 입력하지 않으면 전체 데이터를 스크래핑하므로 주의

---

## 2. Project Description

### Team Name
> 머신일이고 (What The Machine)

### Team Members
- 김민엽: 아키텍처 설계, 검색 알고리즘 및 웹 구현, 프로젝트 종합
- 서민정: 리뷰 감정 분석, 발표자료 작성
- 임은형: 카카오 플레이스 스크래핑 구현, 리뷰 감정 분석
- 정민주: 한글 텍스트 토큰화 및 코사인 유사도 분석
- 차수홍: 한글 텍스트 토큰화 및 코사인 유사도 분석

### Project Period
> Start Date: 2022-04-19   
> End Date: 2022-04-25

---

## 3. Implementation

### Languages:
- Python 3.9.10

### IDE:
- Visual Studio Code
- Jupyter Notebook

### Libraries:
- bs4 0.0.1
- **konlpy** 0.6.0
- numpy 1.22.3
- pandas 1.4.1
- requests 2.27.1
- selenium 4.3.1
- sklearn 0.0
- **streamlit** 1.8.1
- webdriver-manager 3.5.4

---

## 4. Main Classes
- `KakaoAdmin(Admin)`: 카카오 데이터를 기반으로 웹 서비스를 제공하는 관리자 객체
- `KakaoPlaceData(PlaceData)`: 카카오 데이터를 요청하고 처리하는 데이터 객체

---

## 5. Main Methods
- `request`로 시작하는 메소드는 주로 API 또는 웹을 통해 데이터를 수집하거나,   
  전체적인 스크래핑 프로세스를 지휘하는 역할
- `get`으로 시작하는 메소드는 가져온 데이터를 가공하는 역할
- `KakaoPlaceData()`에서 `request_data()`는 전체 스크래핑 과정을 종합한 메인 메소드,   
  크게 API 요청, 셀레니움 스크래핑, 텍스트 토큰화, 리뷰 감정 분석의 네 가지 부분으로 나눠짐
- `KakaoPlaceData()`에서 `dict_to_df()`와 `update_dataframe()`의 조합을 통해   
  `json`으로 불러온 딕셔너리 형태의 데이터를 데이터프레임으로 변환해 저장
- 데이터프레임 변환 시마다 `make_similar_index()`를 사용해 코사인 유사도 배열 생성
- 리뷰 감정을 분석하는 `request_sentiment()` 메소드의 경우 네이버 API를 사용해   
  카카오와 무관하지만, 특별히 둘 곳이 없어 `KakaoPlaceData()` 안에 위치
- `KakaoAdmin()`의 `advanced_search()`를 통해 데이터프레임 상에서 키워드를 검색하고,   
  키워드와 가장 연관성 있는 맛집 정보 및 이와 코사인 유사도가 높은 순으로 정렬된 데이터 반환

---

## 6. Service Data

```python
service_data.json = {
    "places": {
        "젠제로": {
            "address_name": "서울 강남구 삼성동 10-18",
            "category_group_code": "FD6",
            "category_group_name": "음식점",
            "category_name": "음식점 > 간식 > 아이스크림",
            "distance": "",
            "id": "900538186",
            "phone": "02-543-1261",
            "place_url": "http://place.map.kakao.com/900538186",
            "road_address_name": "서울 강남구 선릉로126길 14",
            "x": "127.04324523621",
            "y": "37.5152792229316",
            "bg_image": "https://t1.kakaocdn.net/thumb/...",
            "raiting": 4.4,
            "review_num": 111,
            "blog_num": 246,
            "menu": [...],
            "review": [...],
            "category_token": "...",
            "menu_token": "...",
            "review_token": "...",
            "review_sentiment": [...],
            "positive": 65,
            "negative": 22
        },
        ...
    },
    "errors": {}
}    
```

### API Keys

```python
service_keys = {
    'kakao_rest': '...',
    'kakao_js': '...',
    'naver_clova': ('X-NCP-APIGW-API-KEY-ID','X-NCP-APIGW-API-KEY')
}
```

---

## 7. Error List

### 404 Forbidden
- 카카오 플레이스 페이지에 지속적인 요청을 하다보니 접속이 차단되는 경우가 발생

### Streamlit HTML Problem
- Streamlit으로 웹을 구동할 때 HTML을 텍스트로 인식하는 문제 발생
- 해당 라이브러리에서 HTML을 안전하지 않은 것으로 인식하여 `unsafe_allow_html=True` 설정

---

## 8. Restropective
- 키워드도 토큰화를 진행하여 의미있는 문장인지, 아니면 단순한 단어들의 집합인지 구분하여   
  사용자의 의도에 맞는 결과를 보여주었으면 좋겠지만 시간 부족으로 구현하지 못한 점이 아쉬움
- 사용자의 GPS 상 위치를 파악하여 가까운 맛집 순으로 보여주면 좋겠지만,   
  시간도 부족했고 서비스 지역 자체가 좁아서 향후 서비스 권역을 확대한다면 진행할 것
- 카카오 플레이스 페이지를 셀레니움으로 스크래핑 시 과도한 요청을 보내면   
  `404 Forbidden` 에러가 발생하는 문제로 요청 간 딜레이 시간을 늘려야 했던 아쉬움이 있음
- 네이버 CLOVA Sentiment의 경우 일정 요청 횟수를 넘으면 과금이 되는 문제가 있어   
  자체적인 감정 분석 모델을 개발해야할 필요성을 느낌
- 시간 제약 상 프로젝트에 SQL을 접목시키기 어려워 데이터프레임을 사용해 검색을 구현했지만,   
  향후 서비스 데이터를 DB로 대체해 관리했으면 좋겠음
- 웹 서버를 가동할만한 수준이 안되어 제한된 기능만을 수행할 수 있는 `Streamlit` 모듈로   
  웹을 구현하다보니 디자인 및 기능적으로 만족스럽지 않았음   
  하지만 향후 맥에서 GUI를 구현한다면 해당 라이브러리를 사용해 웹에서 표시하면 편할 것이라 생각
- 현재 살고 있는 광명 지역의 맛집 데이터도 스크래핑해 사용해봤는데 매우 만족
