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


    def set_service_data(self, service_data=dict(), service_df=pd.DataFrame(), size=0):
        """
        서비스 운영에 필요한 데이터를 서버로부터 가져오는 관리자 메소드
        서비스에 사용할 충분한 데이터가 없을 시 카카오 API를 통해 데이터 요청
        향후 다른 플랫폼(네이버 등)에 대한 검색 기능 추가 시 해당 메소드의 범용성을 개선해 상위 클래스 메소드로 변환
        """

        self.service_data = KakaoPlaceData(service_data, service_df)

        if not service_data:
            self.service_info['size'] = size
            self.service_data.request_data(self.service_info, self.local_info)
        elif not len(service_df):
            service_df = self.service_data.dict_to_df(service_data)
            self.service_data.update_dataframe(service_df)


    def update_service_data(self, data_type: type):
        """
        관리자가 보유한 서비스 데이터를 서버에 저장하는 관리자 메소드
        현재는 pd.DataFrame 및 json 타입만 지원
        """

        if type(self.service_data.get_data()) is not dict:
            raise Exception('해당 객체가 요청에 적합한 데이터를 가지고 있지 않습니다.')

        if data_type is json:
            data = self.service_data.get_data()
            with open('service_data.json','w') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            with open(f'log/service_data_{datetime.now()}.json','w') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        elif data_type is pd.DataFrame:
            df = self.service_data.get_dataframe().set_index('식당명')
            df.to_csv('service_data.csv')
            df.to_csv(f'log/service_data_{datetime.now()}.csv')
        else:
            raise Exception(f'{data_type} 타입은 현재 지원하지 않습니다.')


    def advanced_search(self, keywords: list, target=0, display=3, exact=False) -> dict:
        """
        카카오 맛집 데이터프레임 상에서 키워드와 연관성이 있는 맛집 정보를 검색해 결과를 반환하는 메소드
        해당 메소드는 향후 KakaoPlaceData 클래스로 이동 가능
        (현재 1번 진행 중) 불짬뽕 display=10 exact=False 덮밥
        1. 키워드를 포함하는 식당명이 있으면 해당 식당 정보 출력 (1 불짬뽕 삼성점, 2 불짬뽕 강남점)
        2. 보여주는 개수가 부족하면 메뉴에서 키워드를 검색 (3 불짬뽕 메뉴를 갖고 있는 식당, 4 ,,,)
        3. 보여주는 개수가 부족하면 리뷰에서 키워드를 검색 (5 불짬뽕 리뷰를 갖고 있는 식당)
        4. 현재까지 보여준 식당을 기반으로 유사한 식당 보여줌 (불짬뽕 삼성점, 중화반점 강남점)
           1등과 유사한 식당을 보여줌 (5개) > 10개
        """

        if type(self.service_data.get_data()) is not dict:
            raise Exception('해당 객체가 요청에 적합한 데이터를 가지고 있지 않습니다.')

        df = self.service_data.get_dataframe()
        result_df = df.iloc[:0]

        if target == 0: # 식당명, 메뉴 검색
            result_df = self.search_name(df, result_df, keywords, display, exact)
            result_df = self.search_by_row('메뉴', df, result_df, keywords, display, exact)
        elif target == 1: # 식당명 검색
            result_df = self.search_name(df, result_df, keywords, display, exact)
        elif target == 2: # 메뉴 검색
            result_df = self.search_by_row('메뉴', df, result_df, keywords, display, exact)
        elif target == 3: # 리뷰 검색
            result_df = self.search_by_row('리뷰', df, result_df, keywords, display, exact)
        elif target == 4: # 모든 조건 검색
            result_df = self.search_name(df, result_df, keywords, display, exact)
            result_df = self.search_by_row('메뉴', df, result_df, keywords, display, exact)
            result_df = self.search_by_row('리뷰', df, result_df, keywords, display, exact)
        else:
            raise Exception('검색 대상이 유효하지 않습니다.')

        # 검색 결과가 없으면 카카오 API에 키워드를 요청
        if not len(result_df):
            result_df = self.search_api(' '.join(keywords), display)

        # 목록 개수가 요구사항보다 적으면 코사인 유사도 기반 탐색 진행
        if len(result_df) < display:
            column = '식당명'
            place_name = result_df.iloc[0][column]
            similar_df = self.service_data.get_similar_places(column, place_name, display-len(result_df))
            result_df = result_df.append(similar_df)

        return result_df.set_index('식당명').reset_index()
        return result_df.set_index('식당명').T.to_dict()


    def search_name(self, df: pd.DataFrame, result_df: pd.DataFrame, keywords: list, display: int, exact: bool) -> pd.DataFrame:
        if len(result_df) >= display:
            return result_df

        target = df['식당명'].copy()
        match_df = df['식당명'].notnull()

        for keyword in keywords:
            match_df &= (target == keyword) if exact else target.str.contains(keyword)

        result_df = result_df.append(df[match_df]).drop_duplicates(['식당명'])

        return result_df.iloc[:display] if len(result_df) > display else result_df


    def search_by_row(self, column: str, df: pd.DataFrame, result_df: pd.DataFrame, keywords: list, display: int, exact: bool) -> pd.DataFrame:
        if column not in {'메뉴','리뷰'}:
            raise Exception('검색 대상이 유효하지 않습니다.')

        if len(result_df) >= display:
            return result_df

        target = df[column].copy()
        match_df = df['식당명'].notnull()

        match_list = list()

        if exact:
            for target_items in target.iteritems():
                word_list = list()
                for target_item in target_items[1]:
                    word_list += target_item.split()

                match_row = True
                for keyword in keywords:
                    match_keyword = sum([(menu == keyword) for menu in word_list])
                    match_row &= True if match_keyword else False

                match_list.append(match_row)
            match_df &= match_list
        else:
            target = target.apply(lambda x: ' '.join(x))

            for keyword in keywords:
                match_df &= target.str.contains(keyword)

        result_df = result_df.append(df[match_df]).drop_duplicates(['식당명'])

        return result_df.iloc[:display] if len(result_df) > display else result_df


    def search_api(self, keyword: str, display: int) -> pd.DataFrame:
        kakao_data = KakaoPlaceData()
        self.service_info['size'] = 1

        try:
            kakao_data.request_data(self.service_info, self.local_info, keyword)
        except:
            raise Exception(f'{keyword} 검색 결과가 없어요.') # 에러 페이지 생성

        result_df = kakao_data.get_dataframe()
        self.service_data.update_data(kakao_data.get_data())
        self.update_service_data(json)

        return result_df.iloc[:display] if len(result_df) > display else result_df
