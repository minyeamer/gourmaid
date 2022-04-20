import pandas as pd
from data import PlaceData, KakaoPlaceData


class Person(object):

    def __init__(self, name: str, address: str):
        self.name = name
        self.address = address


class Admin(Person):

    def set_service_data(self, service_data=None, size=0, local_info=dict()):
        self.service_data = PlaceData(service_data)


    def get_service_data(self) -> pd.DataFrame:
        return self.service_data.get_data()


class KakaoAdmin(Admin):

    def __init__(self, name: str, address: str, service_key: str, local_info=dict()):
        super().__init__(name, address)
        service_url = 'https://dapi.kakao.com/v2/local/search/keyword.json'
        self.service_info = {'url': service_url, 'key': service_key}
        self.local_info = local_info if local_info else {'si': '', 'gu': '', 'dong': '', 'name': ''}


    def set_service_data(self, service_data=None, size=0):
        """
        서비스 운영에 필요한 빅데이터를 서버로부터 가져오는 관리자 메소드
        서비스에 사용할 충분한 데이터가 없을 시 카카오 API를 통해 데이터 요청
        향후 다른 플랫폼(네이버 등)에 대한 검색 기능 추가 시 해당 메소드의 범용성을 개선해 상위 클래스 메소드로 변환
        """

        self.service_info['size'] = size
        self.service_data = KakaoPlaceData(service_data)

        if not service_data:
            self.service_data.request_data(self.service_info, self.local_info)


    def advanced_search(self, keywords: list, display=3) -> dict:
        """
        카카오 맛집 데이터프레임 상에서 키워드와 연관성이 있는 맛집 정보를 검색해 결과를 반환하는 메소드
        해당 메소드는 향후 KakaoPlacveData 클래스로 이동 가능
        (현재 1번 진행 중)
        1. 단일 키워드를 포함하는 식당명을 검색, 해당 맛집 정보 및 해당 맛집과 연관성이 있는 다른 맛집 정보들 탐색
        2. 키워드를 포함하는 식당명이 없을 경우, 키워드를 포함하는 메뉴명을 검색, 해당 메뉴를 가진 맛집 및 유사 정보 탐색
        3. 키워드를 포함하는 메뉴명이 없을 경우, 키워드를 포함하는 리뷰를 검색, 해당 리뷰를 가진 맛집 및 유사 정보 탐색
        4. 조건에 맞는 검색 결과가 없을 경우, 카카오 API로 키워드를 검색하고 결과와 유사한 맛집 정보 탐색
        5. 단일 키워드가 아닌 전체 키워드 목록에 대한 검색 시도
           만약 키워드 목록을 하나의 문장으로 보고 형태소 분석을 하였을 때 결과가 원본과 다르면 문장을 입력한 것으로 판단
           만약 키워드 목록이 아닌 하나의 문장을 입력했다면 벡터화하여 각각의 리뷰와의 코사인 유사도를 분석
        """

        df = self.get_service_data()

        if df['place_name'].str.contains(keywords[0]).sum():
            return None

        # 조건에 맞는 검색 결과가 없을 경우
        kakao_data = KakaoPlaceData()
        search_result = kakao_data.request_data(self.service_info, self.local_info, keywords[0])
        if search_result['places']:
            return None # 결과와 유사한 맛집 정보 탐색
        else:
            raise Exception(f'{keywords[0]} 검색 결과가 없어요.') # 해당 키워드는 에러 리스트에 저장
