import numpy as np
import pandas as pd
import json
import requests
import time
import re
from webdriver_manager.chrome import ChromeDriverManager 
from selenium.webdriver.chrome.service import Service
from selenium import webdriver
from konlpy.tag import Okt
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import warnings
warnings.filterwarnings("ignore")


class Data:

    def __init__(self, data=dict(), df=pd.DataFrame()):
        self.data = data
        self.df = df.fillna(str())


    def get_data(self) -> dict:
        return self.data


    def get_dataframe(self) -> pd.DataFrame:
        return self.df


    def update_data(self, data: dict):
        self.data.update(data)


    def update_dataframe(self, df: pd.DataFrame):
        self.df = self.df.append(df)


class PlaceData(Data):

    def request_data(self, service_info: dict, local_info: dict, keyword=str()):
        pass


class KakaoPlaceData(PlaceData):

    def __init__(self, data=dict(), df=pd.DataFrame()):
        super().__init__(data, df)
        self.similr_index = self.make_similar_index() if len(df) else None


    def request_data(self, service_info: dict, local_info: dict, keyword=str()):
        """
        카카오 API로부터 장소 정보를 요청하고 추가적인 정보를 스크래핑하는 메인 메소드
        키워드가 없을 경우 빅데이터를 기반으로 모든 장소에 대한 정보 요청
        향후 다른 플랫폼(네이버 등)에 대한 검색 기능 추가 시 해당 메소드의 범용성을 개선해 상위 클래스 메소드로 변환
        """

        place_dict = {'places': list(), 'errors': list()}
        place_list = [keyword] if keyword else self.make_place_list(local_info)

        service_url = service_info['url']
        headers = {"Authorization": service_info['key']}
        size = min(service_info['size'],len(place_list)) if service_info['size'] else None

        service = Service(executable_path=ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service)

        for place_name in place_list[:size]:
            response = requests.get(url=service_url, headers=headers,
                                    params={'query': place_name}).json()
            for place in response['documents']:
                try:
                    if place['address_name'].__contains__(local_info['address']):
                        if place['category_group_name'] == '음식점':
                            place.update(self.request_details(driver, place['place_url']))
                            place.update(self.get_token_dict(
                                place['category_name'], place['menu'], place['review']))
                            place.update(self.get_sentiment_dict(place['review']))
                            place_dict['places'].append(place)
                except:
                    place_dict['errors'].append(place)

        driver.close()
        self.update_data(place_dict)
        self.update_dataframe(self.dict_to_df(place_dict))


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


    # =================================================================================
    # ================================= Scraping Part =================================
    # =================================================================================


    def request_details(self, driver: webdriver.Chrome, place_url: str) -> dict:
        """
        카카오 맛집 페이지에서 별점, 메뉴, 리뷰 데이터를 스크래핑하는 메소드
        스크래핑과 별도로 메뉴와 리뷰에 대한 TF-IDF 벡터값을 계산하여 데이터에 추가
        """

        details = dict()

        driver.get(place_url)
        content_xpath= '/html/body/div[2]/div[2]'
        self.wait_for_xpath(driver, content_xpath, delay=3)

        details_summary = self.get_details_summary(driver)
        details['bg_image'] = details_summary['bg_image']
        details['raiting'] = details_summary['raiting']
        details['review_num'] = details_summary['review_num']
        details['blog_num'] = details_summary['blog_num']
        details['menu'] = self.get_details_menu(driver)
        details['review'] = self.get_details_review(driver, details['review_num'])

        return details


    def get_details_summary(self, driver: webdriver.Chrome) -> dict:
        """
        카카오 맛집 페이지에서 별점, 리뷰 개수, 블로그 리뷰 개수를 추출하는 메소드
        """

        summary = dict()

        try:
            bg_present = driver.find_element_by_class_name('bg_present').get_attribute('style')
            summary['bg_image'] = 'https:' + re.search('url\("(.*)"', bg_present)[1]
        except:
            summary['bg_image'] = ''

        try:
            inner_place = driver.find_element_by_class_name('inner_place')
            evaluation = inner_place.find_element_by_class_name('link_evaluation')
            summary['raiting'] = float(evaluation.find_element_by_tag_name('span').text)
            summary['raiting'] = 0.0 if summary['raiting'] > 5.0 else summary['raiting']
        except:
            summary['raiting'] = 0.0

        try:
            total_evaluation = driver.find_element_by_class_name('total_evaluation')
            summary['review_num'] = int(total_evaluation.find_element_by_tag_name('span').text)
        except:
            summary['review_num'] = 0

        try:
            blog_div = driver.find_element_by_class_name('cont_review')
            summary['blog_num'] = int(blog_div.find_element_by_class_name('num_g').text)
        except:
            summary['blog_num']
        
        return summary


    def get_details_menu(self, driver: webdriver.Chrome) -> list:
        """
        카카오 맛집 페이지에서 메뉴 목록을 추출하는 메소드
        """

        menu_list = list()

        try:
            link_more = driver.find_element_by_class_name('link_more')
            while link_more.text == '메뉴 더보기':
                link_more.click()
        except:
            pass

        try:
            list_menu = driver.find_element_by_class_name('list_menu')
            list_menu = list_menu.find_elements_by_class_name('loss_word')
            menu_list = [menu.text for menu in list_menu]
        except:
            pass
        
        return menu_list


    def get_details_review(self, driver: webdriver.Chrome, review_num: int) -> list:
        """
        카카오 맛집 페이지에서 리뷰 목록을 추출하는 메소드
        """

        review_list = list()
        page_num = int(np.ceil(review_num / 5))

        try:
            for i in range(1,page_num):
                review_div = driver.find_element_by_class_name('evaluation_review')
                comments = review_div.find_elements_by_class_name('txt_comment ')
                [review_list.append(comment.text) if comment.text else None for comment in comments]

                if i < 6:
                    review_div.find_element_by_xpath(f'div/a[{i}]').click()
                elif i % 5 == 0:
                    review_div.find_element_by_xpath(f'div/a[6]').click()
                else:
                    review_div.find_element_by_xpath(f'div/a[{i%5+1}]').click()
                self.wait_for_xpath(driver, 'html')
        except:
            pass

        return review_list


    def wait_for_xpath(self, driver: webdriver.Chrome, xpath: str, delay=1):
        """
        셀레니움 스크래핑 중 딜레이를 발생시키기 위한 메소드
        """

        time.sleep(delay)
        accum_delay = delay

        while True:
            try:
                if driver.find_element_by_xpath(xpath).text:
                    break
            except:
                pass

            if accum_delay > 10:
                raise Exception('카카오 플레이스 페이지를 요청하는 과정에서 문제가 발생했습니다.')

            time.sleep(delay)

            accum_delay += delay
            delay += delay


    # =================================================================================
    # ================================= Tokenize Part =================================
    # =================================================================================


    def get_token_dict(self, category: str, menu: list, review: list) -> dict:
        """
        분류, 메뉴, 리뷰 데이터를 토큰화하는 메소드
        """

        token_dict = dict()

        token_dict['category_token'] = ' '.join(
            [cat.replace(',',' ') for cat in category.split(' > ')[1:]])
        token_dict['menu_token'] = self.get_tokenized_menu(' '.join(menu))
        token_dict['review_token'] = self.get_tokenized_review(' '.join(review))

        return token_dict


    def get_tokenized_menu(self, menu: str) -> str:
        """
        메뉴 데이터를 토큰화하는 메소드
        """

        okt = Okt()

        menu = re.sub('[-=+,#/\?:^.@*\"※~ㆍ!』‘|\(\)\[\]`\'…》\”\“\’·]', '', menu)
        menu = ' '.join(okt.phrases(menu))

        return ' '.join(set(menu.split()))


    def get_tokenized_review(self, review: str) -> str:
        """
        리뷰 데이터를 토큰화하는 메소드
        """

        token_list = list()
        okt = Okt()

        review = re.sub('[-=+,#/\?:^.@*\"※~ㆍ!』‘|\(\)\[\]`\'…》\”\“\’·]', '', review)
        review = re.sub('([ㄱ-ㅎㅏ-ㅣ]+)', '', review)

        for word, pos in okt.pos(review, norm=True, stem=True):
            if pos in ['Noun','Verb','Adjective','Adverb']:
                token_list.append(word)  

        return ' '.join(token_list)


    def make_similar_index(self) -> np.ndarray:
        """
        분류, 메뉴, 리뷰에 대한 코사인 유사도 합을 반환하는 메소드
        """

        if not len(self.df):
            raise Exception('해당 객체가 요청에 적합한 데이터를 가지고 있지 않습니다.')

        category_similarity = self.get_cosine_similarity('분류명 토큰화') * 0.3
        menu_similarity = self.get_cosine_similarity('메뉴 토큰화') * 0.5
        review_similarity = self.get_cosine_similarity('리뷰 토큰화') * 1
        similarity = category_similarity + menu_similarity + review_similarity
        return similarity.argsort()[:, ::-1]


    def get_cosine_similarity(self, column: str) -> np.ndarray:
        """
        특정 열에 대한 코사인 유사도를 반환하는 메소드
        """

        tokenized_data = self.df[column].fillna('')

        if column in {'분류명 토큰화', '메뉴 토큰화'}:
            vectorizer = CountVectorizer(min_df=0, ngram_range=(1,2))
            array = vectorizer.fit_transform(tokenized_data)
            return cosine_similarity(array, array)
        elif column in {'리뷰 토큰화'}:
            vectorizer = TfidfVectorizer()
            array = vectorizer.fit_transform(tokenized_data).todense()
            return cosine_similarity(array, array)
        else:
            raise Exception(f'대상이 유효하지 않습니다.')


    def get_similar_places(self, result_df: pd.DataFrame, column: str, display: int) -> pd.DataFrame:
        """
        특정 조건을 만족하는 행과 유사한 데이터프레임을 반환하는 메소드
        """

        place_value = result_df.iloc[0][column]
        place_index = self.df[self.df[column] == place_value].index.values
        max_index = min(display*2, len(self.df))

        similar_df = self.df.loc[self.similr_index[place_index,1:max_index][0]]
        result_df = result_df.append(similar_df)
        result_df.drop_duplicates(['식당명'], inplace=True)

        return result_df.iloc[:display] if len(result_df) > display else result_df


    # =================================================================================
    # =================================== Data Part ===================================
    # =================================================================================


    def get_sentiment_dict(self, review: list) -> dict:
        """
        리뷰의 감정을 분류하고 각 분류별 개수를 반환하는 메소드
        """

        sentiment_dict = dict()

        sentiment_dict['positive'] = 0
        sentiment_dict['negative'] = 0

        return sentiment_dict


    def dict_to_df(self, data: dict) -> pd.DataFrame:
        """
        딕셔너리 형태의 스크래핑 결과를 데이터프레임으로 변환하는 메소드
        """

        if not data['places']:
            raise Exception('해당 객체가 요청에 적합한 데이터를 가지고 있지 않습니다.')

        df = pd.DataFrame(data['places'])
        df.drop(['category_group_code','category_group_name','distance','id'], axis=1, inplace=True)

        kr_dict = dict()
        kr_dict['place_name'] = '식당명'
        kr_dict['address_name'] = '지번 주소'
        kr_dict['category_name'] = '분류명'
        kr_dict['phone'] = '전화번호'
        kr_dict['place_url'] = '웹페이지 주소'
        kr_dict['road_address_name'] = '도로명 주소'
        kr_dict['bg_image'] = '이미지 주소'
        kr_dict['raiting'] = '별점'
        kr_dict['review_num'] = '리뷰 수'
        kr_dict['blog_num'] = '블로그 리뷰 수'
        kr_dict['menu'] = '메뉴'
        kr_dict['review'] = '리뷰'
        kr_dict['category_token'] = '분류명 토큰화'
        kr_dict['menu_token'] = '메뉴 토큰화'
        kr_dict['review_token'] = '리뷰 토큰화'
        kr_dict['positive'] = '긍정 리뷰 수'
        kr_dict['negative'] = '부정 리뷰 수'

        return df.rename(columns=kr_dict)


    def update_data(self, data: dict):
        """
        딕셔너리를 업데이트하는 메소드
        """

        if not self.data:
            self.data.update(data)
        else:
            self.data['places'].append(data['places'])
            self.data['errors'].append(data['errors'])


    def update_dataframe(self, df: pd.DataFrame):
        """
        데이터프레임 및 코사인 유사도 배열을 업데이트하는 메소드
        """

        self.df = self.df.append(df)
        self.df['인기도'] = self.df['별점']**1.2 + np.log(self.df['리뷰 수'])
        self.df.sort_values(by=['인기도','식당명'], ascending=[False,True], inplace=True)
        del self.df['인기도']
        self.df.drop_duplicates(['식당명'], inplace=True)
        self.df = self.df.set_index('식당명').reset_index()
        self.similr_index = self.make_similar_index()
