import numpy as np
import pandas as pd
import requests
from webdriver_manager.chrome import ChromeDriverManager 
from selenium.webdriver.chrome.service import Service 
from selenium import webdriver
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import warnings
warnings.filterwarnings("ignore")


class Data:

    def __init__(self, data: pd.DataFrame):
        self.data = data


    def get_data(self) -> pd.DataFrame:
        return self.data


class PlaceData(Data):

    def request_data(self, service_info: dict, local_info: dict, keywords=list()) -> dict:
        pass


class KakaoPlaceData(PlaceData):

    def request_data(self, service_info: dict, local_info: dict, keywords=list()) -> pd.DataFrame:
        """
        카카오 API로부터 장소 정보를 요청하고 추가적인 정보를 스크래핑하는 메인 메소드
        키워드가 없을 경우 빅데이터를 기반으로 모든 장소에 대한 정보 요청
        향후 다른 플랫폼(네이버 등)에 대한 검색 기능 추가 시 해당 메소드의 범용성을 개선해 상위 클래스 메소드로 변환

        service_info.keys() = ['url', 'key', 'size']
        local_info.keys() = ['si', 'gu', 'dong', 'address']
        """

        place_dict = {'places': list()}
        place_list = keywords if keywords else self.make_place_list(local_info)

        service_url = service_info['url']
        headers = {"Authorization": service_info['key']}
        size = min(service_info['size'],len(place_list)) if service_info['size'] else None

        for place_name in place_list[:size]:
            response = requests.get(url=service_url, headers=headers,
                                    params={'query': place_name}).json()
            for place in response['documents']:
                try:
                    if place['address_name'].__contains__(local_info['address']):
                        if place['category_group_name'] == '음식점':
                            place.update(self.request_details(place['place_url']))
                            place_dict['places'].append(place)
                except:
                    pass

        if place_dict['places']:
            self.data =  self.reformat_dataframe(pd.DataFrame(place_dict['places']))
            self.data.to_csv('123.csv')


    def make_place_list(self, local_info: dict) -> list:
        """
        빅데이터를 기반으로 서비스 지역 내 장소 목록을 반환하는 메소드
        현재는 전국 인허가 음식점 빅데이터를 서버로부터 직접 가져와 수동으로 전처리 진행
        """

        # 용량 문제로 원본 파일 미첨부 @ https://www.localdata.go.kr/datafile/each/07_24_05_P_CSV.zip
        place_df = pd.read_csv('debugs/rest.csv', encoding='cp949')

        place_df = place_df[place_df['영업상태명'] != '폐업']
        place_df = place_df[['도로명전체주소','사업장명']]
        place_df = place_df[(place_df['도로명전체주소'].notnull()) &
                            (place_df['도로명전체주소'].str.contains(local_info['si'])) &
                            (place_df['도로명전체주소'].str.contains(local_info['gu'])) &
                            (place_df['도로명전체주소'].str.contains(local_info['dong']))]

        return place_df['사업장명'].tolist()


    def request_details(self, place_url: str) -> dict:
        """
        카카오 맛집 페이지에서 별점, 메뉴, 리뷰 데이터를 스크래핑하는 메소드
        스크래핑과 별도로 메뉴와 리뷰에 대한 TF-IDF 벡터값을 계산하여 데이터에 추가
        """

        details = dict()

        # 카카오 맛집 페이지 스크래핑

        details['rating'] = str()
        details['menu'] = list()
        details['review'] = list()
        details['vector'] = self.make_vector('menu', 'review')
        details['temp'] = self.calc_temp('review')

        return details


    def make_vector(self, menu: list, review: list) -> np.array:
        """
        메뉴와 리뷰 데이터를 TF-IDF 벡터화하는 메소드
        (현재 1번 진행 중)
        1. 메뉴와 리뷰를 토큰화하고 분리된 목록을 하나로 합쳐서 벡터화 (메뉴와 리뷰를 하나의 문장으로 봄)
        2. 메뉴와 리뷰를 토큰화하고 각각을 벡터화 (메뉴와 리뷰에 대한 두 개의 벡터를 반환)
        3. 메뉴를 의미있는 단어로 토큰화하고 별도로 토큰화된 리뷰와 합쳐서 벡터화
        """

        vector = None


    def calc_temp(self, review: list) -> int:
        """
        리뷰의 긍정/부정 정도를 종합해 0-100 사이의 온도 수치로 변환하는 메소드
        """
        temp = 36.5


    def reformat_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        df.drop(['category_group_code','category_group_name','distance','id'], axis=1)
        df['category_name'] = df['category_name'].apply(lambda x: str(x).split(' > ')[-1])

        kr_dict = dict()
        kr_dict['address_name'] = '지번주소'
        kr_dict['category_name'] = '분류명'
        kr_dict['phone'] = '전화번호'
        kr_dict['place_name'] = '식당명'
        kr_dict['place_url'] = '사이트주소'
        kr_dict['road_address_name'] = '도로명주소'
        df.rename(columns=kr_dict, inplace=True)

        return df.set_index('식당명')
