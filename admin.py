from datetime import datetime
import json
import pandas as pd
import re
from data import KakaoPlaceData


class Person(object):

    def __init__(self, name: str, address: str):
        self.name = name
        self.address = address


class Admin(Person):

    def __init__(self, name: str, address: str):
        super().__init__(name, address)


class KakaoAdmin(Admin):

    def __init__(self, name: str, address: str, service_keys: dict, local_info=dict()):
        super().__init__(name, address)
        service_urls = dict()
        service_urls['kakao_search'] = 'https://dapi.kakao.com/v2/local/search/keyword.json'
        service_urls['kakao_map'] = 'https://dapi.kakao.com/v2/maps/sdk.js'
        service_urls['naver_clova'] = 'https://naveropenapi.apigw.ntruss.com/sentiment-analysis/v1/analyze'
        self.service_info = {'urls': service_urls, 'keys': service_keys}
        self.local_info = local_info if local_info else {'si': '', 'gu': '', 'dong': '', 'name': ['']}


    def set_service_data(self, service_data=dict(), service_df=pd.DataFrame(), size=0):
        """
        서비스 운영에 필요한 데이터를 서버로부터 가져오는 관리자 메소드
        서비스에 사용할 충분한 데이터가 없을 시 카카오 API를 통해 데이터 요청
        향후 다른 플랫폼(네이버 등)에 대한 검색 기능 추가 시 해당 메소드의 범용성을 개선해 상위 클래스 메소드로 변환
        """

        self.service_data = KakaoPlaceData(service_data, service_df)

        if not service_data:
            self.service_data.request_data(self.service_info, self.local_info, size=size)
        elif not len(service_df):
            service_df = self.service_data.dict_to_df(service_data['places'], self.local_info)
            self.service_data.update_dataframe(service_df)


    def update_service_data(self, data_type: type):
        """
        관리자가 보유한 서비스 데이터를 서버에 저장하는 관리자 메소드
        현재는 json 및 pd.DataFrame 타입만 지원
        """

        if type(self.service_data.get_data()) is not dict:
            raise Exception('해당 객체가 요청에 적합한 데이터를 가지고 있지 않습니다.')

        if data_type is json:
            data = self.service_data.get_data()
            with open('data/service_data.json','w') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            with open(f'log/service_data_{datetime.now()}.json','w') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        elif data_type is pd.DataFrame:
            df = self.service_data.get_dataframe().set_index('식당명')
            df.to_csv('data/service_data.csv')
            df.to_csv(f'log/service_data_{datetime.now()}.csv')
        else:
            raise Exception(f'{data_type} 타입은 현재 지원하지 않습니다.')

        print(f'[{datetime.now()}] {data_type} 서비스 데이터가 업데이트 되었습니다.') # 로그 기록


    def advanced_search(self, keywords: list, target='일반 검색', display=None, exact=False) -> dict:
        """
        카카오 맛집 데이터프레임 상에서 키워드와 연관성이 있는 맛집 정보를 검색해 결과를 반환하는 메소드
        해당 메소드는 향후 KakaoPlaceData 클래스로 이동 가능
        """

        if type(self.service_data.get_data()) is not dict:
            raise Exception('해당 객체가 요청에 적합한 데이터를 가지고 있지 않습니다.')

        df = self.service_data.get_dataframe()
        result_df = df.iloc[:0]
        display = len(df) if not display else display

        if not keywords:
            return df.iloc[:display]

        if target == '일반 검색': # 식당명, 메뉴 검색
            result_df = self.search_name(df, result_df, keywords, display, exact)
            result_df = self.search_by_row('메뉴', df, result_df, keywords, display, exact)
        elif target == '식당명 검색': # 식당명 검색
            result_df = self.search_name(df, result_df, keywords, display, exact)
        elif target == '메뉴 검색': # 메뉴 검색
            result_df = self.search_by_row('메뉴', df, result_df, keywords, display, exact)
        elif target == '리뷰 검색': # 리뷰 검색
            result_df = self.search_by_row('리뷰', df, result_df, keywords, display, exact)
        elif target == '전체 검색': # 모든 조건 검색
            result_df = self.search_name(df, result_df, keywords, display, exact)
            result_df = self.search_by_row('메뉴', df, result_df, keywords, display, exact)
            result_df = self.search_by_row('리뷰', df, result_df, keywords, display, exact)
        else:
            raise Exception('검색 대상이 유효하지 않습니다.')

        # 검색 결과가 없으면 전체 검색을 진행해보고 카카오 API에 키워드를 요청
        if not len(result_df):
            verify_df = self.search_name(df, result_df, keywords, 1, exact)
            verify_df = self.search_by_row('메뉴', df, verify_df, keywords, 1, exact)
            verify_df = self.search_by_row('리뷰', df, verify_df, keywords, 1, exact)
            if not len(verify_df):
                result_df = self.search_api(' '.join(keywords), display)
            else:
                raise Exception('{} 검색 결과가 없어요.'.format(' '.join(keywords)))

        # 목록 개수가 요구사항보다 적으면 코사인 유사도 기반 탐색 진행
        if len(result_df) < display:
            result_df = self.service_data.get_similar_places(result_df, '식당명', display)

        return result_df.set_index('식당명').reset_index() # 데이터프레임 반환
        return result_df.set_index('식당명').T.to_dict() # 딕셔너리 반환


    def search_name(self, df: pd.DataFrame, result_df: pd.DataFrame, keywords: list, display: int, exact: bool) -> pd.DataFrame:
        """
        카카오 맛집 데이터프레임 상에서 키워드와 연관성이 있는 식당명을 검색해 결과를 반환하는 메소드
        """

        if len(result_df) >= display:
            return result_df

        target = df['식당명'].copy()
        match_df = df['식당명'].notnull() if exact else df['식당명'].isnull()

        if exact:
            for keyword in keywords:
                    match_df &= (target == keyword)
        else:
            for keyword in keywords:
                    match_df |= target.str.contains(keyword)

        result_df = result_df.append(df[match_df])
        result_df.drop_duplicates(['식당명'], inplace=True)

        return result_df.iloc[:display] if len(result_df) > display else result_df


    def search_by_row(self, column: str, df: pd.DataFrame, result_df: pd.DataFrame, keywords: list, display: int, exact: bool) -> pd.DataFrame:
        """
        카카오 맛집 데이터프레임 상에서 키워드와 연관성이 있는 목록 내 데이터를 검색해 결과를 반환하는 메소드
        """

        if column not in {'메뉴','리뷰'}:
            raise Exception('검색 대상이 유효하지 않습니다.')

        if len(result_df) >= display:
            return result_df

        target = df[column].copy()
        match_df = df['식당명'].notnull() if exact else df['식당명'].isnull()

        match_list = list()

        for target_items in target.iteritems():
            # 데이터프레임을 직접 가져올 때 리스트가 문자열로 합쳐지는 문제에 대한 대비책
            # try:
            #     target_items[1].replace('"',"'")
            #     target_items = re.search("\['(.*)'\]",target_items[1])
            #     target_items = target_items[1].split("', '")
            # except:
            #     match_list.append(False)
            #     continue

            word_list = list()
            for target_item in target_items[1]:
                word_list += target_item.split()

            for keyword in keywords:
                if exact:
                    match_row = True
                    match_keyword = sum([(word == keyword) for word in word_list])
                    match_row &= True if match_keyword else False
                else:
                    match_row = False
                    match_keyword = sum([word.__contains__(keyword) for word in word_list])
                    match_row |= True if match_keyword else False

            match_list.append(match_row)

        if exact:
            for keyword in keywords:
                    match_df &= match_list
        else:
            for keyword in keywords:
                    match_df |= match_list

        match_df &= match_list

        result_df = result_df.append(df[match_df])
        result_df.drop_duplicates(['식당명'], inplace=True)

        return result_df.iloc[:display] if len(result_df) > display else result_df


    def search_api(self, keyword: str, display: int) -> pd.DataFrame:
        """
        카카오 API에 키워드와 연관성이 있는 장소를 검색한 결과를 반환하는 메소드
        """

        kakao_data = KakaoPlaceData()

        try:
            kakao_data.request_data(self.service_info, self.local_info, keyword)
        except:
            raise Exception(f'{keyword} 검색 결과가 없어요.')

        result_df = kakao_data.get_dataframe()
        self.service_data.update_data(kakao_data.get_data())
        self.update_service_data(json)

        return result_df.iloc[:display] if len(result_df) > display else result_df
