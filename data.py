import numpy as np
import pandas as pd
import json
import requests
import time
from webdriver_manager.chrome import ChromeDriverManager 
from selenium.webdriver.chrome.service import Service 
from selenium import webdriver
from konlpy.tag import Okt
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import warnings
warnings.filterwarnings("ignore")


class Data:

    def __init__(self, data=None):
        self.data = data


    def get_data(self) -> dict:
        return self.data


    def get_dataframe(self) -> pd.DataFrame:
        return self.data


class PlaceData(Data):

    def request_data(self, service_info: dict, local_info: dict, keywords=list()):
        pass


class KakaoPlaceData(PlaceData):

    def request_data(self, service_info: dict, local_info: dict, keyword=''):
        """
        카카오 API로부터 장소 정보를 요청하고 추가적인 정보를 스크래핑하는 메인 메소드
        키워드가 없을 경우 빅데이터를 기반으로 모든 장소에 대한 정보 요청
        향후 다른 플랫폼(네이버 등)에 대한 검색 기능 추가 시 해당 메소드의 범용성을 개선해 상위 클래스 메소드로 변환

        service_info.keys() = ['url', 'key', 'size']
        local_info.keys() = ['si', 'gu', 'dong', 'address']
        """

        place_dict = {'places': list(), 'errors': list()}
        place_list = [keyword] if keyword else self.make_place_list(local_info)

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
                            place.update(self.get_token_dict(place['menu'], place['review']))
                            place.update(self.get_temp_dict(place['review']))
                            place_dict['places'].append(place)
                except:
                    place_dict['errors'].append(place)

        self.data = place_dict


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

        service = Service(executable_path=ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service)

        driver.get(place_url)
        content_xpath= '/html/body/div[2]/div[2]'
        self.wait_for_xpath(driver, content_xpath)

        details_num = self.get_details_num(driver)
        details['raiting'] = details_num[0]
        details['review_num'] = details_num[1]
        details['blog_num'] = details_num[2]
        details['menu'] = self.get_details_menu(driver)
        details['review'] = self.get_details_review(driver, details_num[1])

        return details


    def get_details_num(self, driver: webdriver.Chrome) -> tuple:
        """
        카카오 맛집 페이지에서 별점, 리뷰 개수, 블로그 리뷰 개수를 추출하는 메소드
        """

        try:
            inner_place = driver.find_element_by_class_name('inner_place')
            evaluation = inner_place.find_element_by_class_name('link_evaluation')
            raiting = float(evaluation.find_element_by_tag_name('span').text)
        except:
            raiting = 0.0

        try:
            total_evaluation = driver.find_element_by_class_name('total_evaluation')
            review_num = int(total_evaluation.find_element_by_tag_name('span').text)
        except:
            review_num = 0

        try:
            blog_div = driver.find_element_by_class_name('cont_review')
            blog_num = int(blog_div.find_element_by_class_name('num_g').text)
        except:
            blog_num
        
        return (raiting, review_num, blog_num)



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
                review_list += [comment.text for comment in comments]

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


    def wait_for_xpath(self, driver: webdriver.Chrome, xpath: str, delay=0.5):
        """
        셀레니움 스크래핑 중 딜레이를 발생시키기 위한 메소드
        """

        time.sleep(delay)
        accum_delay = delay

        while not driver.find_element_by_xpath(xpath).text:
            if accum_delay > 10:
                raise Exception('카카오 플레이스 페이지를 요청하는 과정에서 문제가 발생했습니다.')

            time.sleep(delay)

            accum_delay += delay
            delay += delay


    def get_token_dict(self, menu: list, review: list) -> dict:
        """
        메뉴와 리뷰 데이터를 토큰화하는 메소드
        """

        vector_dict = dict()

        reviews=[]
        clean_review_tokenized=[]
        clean_menu_tokenized=[]
        total=[]

        menu_okt = Okt()
        menu=' '.join(str(s) for s in menu)
        clean_menu=re.sub('[-=+,#/\?:^.@*\"※~ㆍ!』‘|\(\)\[\]`\'…》\”\“\’·]', '', menu)
        clean_menu = re.sub(r'[0-9]+', '', clean_menu)
        
        review=' '.join(str(s) for s in review)
        clean_review=re.sub('[-=+,#/\?:^.@*\"※~ㆍ!』‘|\(\)\[\]`\'…》\”\“\’·]', '', review)
        clean_review=re.sub("([ㄱ-ㅎㅏ-ㅣ]+)","",clean_review)
        
        print(clean_menu)
        clean_menu_tokenized.append(clean_menu)

        # total.append(" ".join(menu_okt.phrases(clean_menu))+" "+select_tokenize(review_tokenize(clean_review)))
        total.append(" ".join(menu_okt.phrases(clean_menu)))
        # total.append(select_tokenize(review_tokenize(clean_review)))

        count_vect_menu = CountVectorizer(min_df=0, ngram_range=(1,2))
        place_menu = count_vect_menu.fit_transform(total) 
        place_simi_menu = cosine_similarity(place_menu, place_menu) 
        place_simi_menu_sorted_ind = place_simi_menu.argsort()[0, ::-1]
        place_simi_menu_sorted_ind.reshape(-1)

        [print(clean_menu_tokenized[i]) for i in [0,2,3,1]]

        return vector_dict


    def review_tokenize(review : str) -> tuple:
        okt = Okt()
        Okt_morphs=okt.pos(review,norm=True,stem=True)  # 형태소 분석
        return Okt_morphs


    def select_tokenize(tokenize : tuple) -> str:
        filter_review=""
        for word, pos in tokenize:
    #        if pos in STOP_WORDS: #리뷰들 보면서 불용어 직접 추가해야 됨
    #            pass
            if pos == 'Noun' or pos == "Verb" or pos == "Adjective" or pos == "Adverb":
                filter_review=filter_review+" "+word        
        return filter_review



    def get_temp_dict(self, review: list) -> dict:
        """
        리뷰의 긍정/부정 정도를 종합해 0-100 사이의 온도 수치로 변환하는 메소드
        """
        temp_dict = dict()

        temp = 36.5
        temp_dict['temp'] = temp

        return temp_dict


    def get_dataframe(self) -> pd.DataFrame:
        if type(self.data) is not dict or not self.data['places']:
            raise Exception('해당 객체가 요청에 적합한 데이터를 가지고 있지 않습니다.')

        df = pd.DataFrame(self.data['places'])
        df.drop(['category_group_code','category_group_name','distance','id'], axis=1)
        df.sort_values(by=['raiting','place_name'], ascending=[False,True], inplace=True)

        kr_dict = dict()
        kr_dict['place_name'] = '식당명'
        kr_dict['address_name'] = '지번주소'
        kr_dict['category_name'] = '분류명'
        kr_dict['phone'] = '전화번호'
        kr_dict['place_url'] = '사이트주소'
        kr_dict['road_address_name'] = '도로명주소'
        kr_dict['raiting'] = '별점'
        kr_dict['review_num'] = '리뷰수'
        kr_dict['blog_num'] = '블로그리뷰수'
        kr_dict['menu'] = '메뉴'
        kr_dict['review'] = '리뷰'
        # kr_dict['menu_token'] = '메뉴토큰'
        # kr_dict['review_token'] = '리뷰토큰'
        # kr_dict['temp'] = '온도'
        df.rename(columns=kr_dict, inplace=True)

        return df


# ============================================================================================
# ======================================== DEBUG CODE ========================================
# ============================================================================================


def debug_request_data(size=0, keywords=list()):
    """
    기존 request_data() 메소드에서 스크래핑 부분까지만 진행하고 결과를 JSON 파일로 저장하는 디버그용 함수
    """

    from api import get_kakao_key
    kakao_data = KakaoPlaceData()

    place_dict = {'places': list(), 'errors': list()}
    local_info = {'si': '서울특별시', 'gu': '강남구', 'dong': '삼성동', 'address': '서울 강남구 삼성동'}
    place_list = keywords if keywords else kakao_data.make_place_list(local_info)

    service_url = 'https://dapi.kakao.com/v2/local/search/keyword.json'
    headers = {"Authorization": get_kakao_key()}
    size = min(size,len(place_list)) if size else None

    for place_name in place_list[:size]:
        response = requests.get(url=service_url, headers=headers,
                                params={'query': place_name}).json()
        for place in response['documents']:
            try:
                if place['address_name'].__contains__(local_info['address']):
                    if place['category_group_name'] == '음식점':
                        place.update(kakao_data.request_details(place['place_url']))
                        place_dict['places'].append(place)
            except:
                place_dict['errors'].append(place)

    with open('./kakao_data.json','w') as f:
        json.dump(place_dict, f, ensure_ascii=False, indent=4)


def debug_merge_data():
    """
    API 요청 결과와 스크래핑한 결과를 합치고 저장하는 함수
    """

    kakao_data = {'documents': list(), 'errors': list()}

    with open('debugs/api_result.json','r', encoding='UTF-8') as f:
        api_data = json.load(f)

    with open('debugs/scraping_result.json','r', encoding='UTF-8') as f:
        scraping_data = json.load(f)

    for place in api_data['documents']:
        try:
            place['raiting'] = np.mean(list(map(int, scraping_data[place['place_name']]['별점'])))
            place['raiting'] = np.nan_to_num(place['raiting'])
            place['menu'] = scraping_data[place['place_name']]['메뉴']
            place['review'] = scraping_data[place['place_name']]['리뷰']
            kakao_data['documents'].append(place)
        except:
            kakao_data['errors'].append(place) # 별점 3.0 이하 식당

    with open('kakao_data.json','w') as f:
        json.dump(kakao_data, f, ensure_ascii=False, indent=4)


def debug_request_vector():
    """
    스크래핑한 JSON 파일을 기반으로 TF-IDF 벡터값과 긍정/부정
    """

    with open('debugs/kakao_data.json','r', encoding='UTF-8') as f:
        kakao_data = json.load(f)

    for place in kakao_data['documents']:
        kakao = KakaoPlaceData()
        place.update(kakao.get_token_dict(place['menu'], place['review']))
        # place.update(kakao.get_temp_dict(place['review']))
        kakao_data['documents'].append(place)

    with open('service_data.json','w') as f:
        json.dump(kakao_data, f, ensure_ascii=False, indent=4)
