import enum
import json
import pandas as pd
from datetime import datetime
from data import KakaoPlaceData


class Person(object):

    def __init__(self, name: str, address: str):
        self.name = name
        self.address = address


class Admin(Person):

    def __init__(self, name: str, address: str):
        super().__init__(name, address)


class KakaoAdmin(Admin):

    def __init__(self, name: str, address: str, service_key: str, local_info=dict()):
        super().__init__(name, address)
        service_url = 'https://dapi.kakao.com/v2/local/search/keyword.json'
        self.service_info = {'url': service_url, 'key': service_key}
        self.local_info = local_info if local_info else {'si': '', 'gu': '', 'dong': '', 'name': ''}


    def set_service_data(self, service_data=None, size=0):
        """
        서비스 운영에 필요한 데이터를 서버로부터 가져오는 관리자 메소드
        서비스에 사용할 충분한 데이터가 없을 시 카카오 API를 통해 데이터 요청
        향후 다른 플랫폼(네이버 등)에 대한 검색 기능 추가 시 해당 메소드의 범용성을 개선해 상위 클래스 메소드로 변환
        """

        self.service_info['size'] = size
        self.service_data = service_data

        if not service_data:
            kakao_data = KakaoPlaceData()
            kakao_data.request_data(self.service_info, self.local_info)
            self.data = kakao_data.get_data()


    def update_service_data(self, data_type: type):
        """
        관리자가 보유한 서비스 데이터를 서버에 저장하는 관리자 메소드
        현재는 pd.DataFrame 및 json 타입만 지원
        """

        if type(self.service_data) is not dict:
            raise Exception('해당 객체가 요청에 적합한 데이터를 가지고 있지 않습니다.')

        if data_type is json:
            with open('service_data.json','w') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
            with open(f'log/service_data_{datetime.now()}.json','w') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
        elif data_type is pd.DataFrame:
            kakao_data = KakaoPlaceData(self.data)
            df = kakao_data.get_dataframe().set_index('식당명')
            df.to_csv('service_data.csv')
            df.to_csv(f'log/service_data_{datetime.now()}.csv')
        else:
            raise Exception(f'{data_type} 타입은 현재 지원하지 않습니다.')


    def advanced_search(self, keyword: str, target=0, display=3, exact=False) -> dict:
        """
        카카오 맛집 데이터프레임 상에서 키워드와 연관성이 있는 맛집 정보를 검색해 결과를 반환하는 메소드
        해당 메소드는 향후 KakaoPlaceData 클래스로 이동 가능
        (현재 1번 진행 중) 불짬뽕 display=10 exact=False 덮밥
        1. 키워드를 포함하는 식당명이 있으면 해당 식당 정보 출력 (1 불짬뽕 삼성점, 2 불짬뽕 강남점)
        2. 보여주는 개수가 부족하면 메뉴에서 키워드를 검색 (3 불짬뽕 메뉴를 갖고 있는 식당, 4 ,,,)
        3. 보여주는 개수가 부족하면 리뷰에서 키워드를 검색 (5 불짬뽕 리뷰를 갖고 있는 식당)
        4. 현재까지 보여준 식당을 기반으로 유사한 식당 보여줌 (불짬뽕 삼성점, 중화반점 강남점)
           1등과 유사한 식당을 보여줌 (5개) > 10개
        
        1. 키워드를 포함하는 식당명이 없으면
        2. 메뉴가 식당명을 대신 (1 불짬뽕 메뉴를 갖고 있는 식당)

        식당 하나를 기준으로 했을 때 유사도 = 분류 * 가중치 + 메뉴 * 가중치 + 리뷰 * 가중치

        target 0. 전체 검색
        target 1. 식당명 검색
        target 2. 메뉴 검색
        """

        if type(self.service_data) is not dict:
            raise Exception('해당 객체가 요청에 적합한 데이터를 가지고 있지 않습니다.')

        result = dict()
        if target == 0:
            result['places'] = self.search_all(keyword, display, exact)
        elif target == 1:
            result['places'] = self.search_name(keyword, display, exact)
        elif target == 2:
            result['places'] = self.search_menu(keyword, display, exact)
        else:
            raise Exception('검색 대상이 유효하지 않습니다.')

        # 검색 결과가 없으면 카카오 API에 키워드를 요청
        if not result['places']:
            kakao_data = KakaoPlaceData()
            kakao_data.request_data(self.service_info, self.local_info, keyword)
            if not kakao_data.get_data()['places']:
                raise Exception(f'{keyword} 검색 결과가 없어요.')
            self.data.update(kakao_data.get_data())
            self.update_service_data(json)
            result['places'] = kakao_data.get_data()['places']

        # 목록 개수가 요구사항보다 적으면 코사인 유사도 기반 탐색 진행
        if len(result) < display:
            result['places'] += []


    def search_all(self, keyword: str, display: int, exact: bool, result=list()) -> list:
        if len(result) >= display:
            return result

        kakao_data = KakaoPlaceData(self.data)
        df = kakao_data.get_dataframe()

        result += self.search_name(keyword, display, exact, result)
        result += self.search_menu(keyword, display, exact, result)
        result += self.search_review(keyword, display, exact, result)

        return result[:display] if len(result) > display else result


    def search_name(self, keyword: str, display: int, exact: bool, result=list()) -> list:
        if len(result) >= display:
            return result

        kakao_data = KakaoPlaceData(self.data)
        df = kakao_data.get_dataframe()

        target = df['식당명']
        df = df[(target == keyword)] if exact else df[target.str.contains(keyword)]
        places = df.set_index('식당명').T.to_dict()

        if places:
            result = [ {key: value} for key, value in places.items() ]

        return result[:display] if len(result) > display else result


    def search_menu(self, keyword: str, display: int, exact: bool, result=list()) -> list:
        if len(result) >= display:
            return result

        kakao_data = KakaoPlaceData(self.data)
        df = kakao_data.get_dataframe()

        target = df['메뉴'] # 아래 코드 수정 필요
        df = df[(target == keyword)] if exact else df[target.str.contains(keyword)]
        places = df.set_index('식당명').T.to_dict()

        if places:
            result = [ {key: value} for key, value in places.items() ]

        return result[:display] if len(result) > display else result


    def search_review(self, keyword: str, display: int, exact: bool, result=list()) -> list:
        if len(result) >= display:
            return result

        kakao_data = KakaoPlaceData(self.data)
        df = kakao_data.get_dataframe()

        target = df['리뷰'] # 아래 코드 수정 필요
        df = df[(target == keyword)] if exact else df[target.str.contains(keyword)]
        places = df.set_index('식당명').T.to_dict()

        if places:
            result = [ {key: value} for key, value in places.items() ]

        return result[:display] if len(result) > display else result


        """
        1. 단일 키워드를 포함하는 식당명을 검색, 해당 맛집 정보 및 해당 맛집과 연관성이 있는 다른 맛집 정보들 탐색
        2. 키워드를 포함하는 식당명이 없을 경우, 키워드를 포함하는 메뉴명을 검색,
                                                                                해당 메뉴를 가진 맛집 및 유사 정보 탐색
        3. 키워드를 포함하는 메뉴명이 없을 경우, 키워드를 포함하는 리뷰를 검색,
                                                                            해당 리뷰를 가진 맛집 및 유사 정보 탐색
        4. 조건에 맞는 검색 결과가 없을 경우,
                                                                카카오 API로 키워드를 검색하고 결과와 유사한 맛집 정보 탐색
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
