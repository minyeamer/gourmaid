import json
from admin import KakaoAdmin
from api import get_kakao_key


def main():
    """
    서비스 데이터를 관리하는 관리자 객체를 생성하고 검색 서비스를 실행하는 메인 함수
    """

    # api.get_kakao_key()는 개인정보 문제로 숨김 처리
    kakao_api_key = get_kakao_key()

    # 프로젝트 시간 제약에 의해 서비스 지역을 서울시 강남구 삼성동으로 한정
    local_info = {'si': '서울특별시', 'gu': '강남구', 'dong': '삼성동', 'address': '서울 강남구 삼성동'}

    admin = KakaoAdmin('minyeamer','abcd@likelion.org',kakao_api_key,local_info)

    # 스크래핑이 필요한 경우 (디버그 시 size 파라미터를 통해 요청할 데이터 수 설정)
    admin.set_service_data()

    # 스크래핑한 데이터가 있을 경우
    with open('service_data.json','r', encoding='UTF-8') as f:
        service_data = json.load(f)
    admin.set_service_data(service_data)

    # 검색 요청이 있으면
    if True:
        keyword = input('검색어를 입력해주세요. ')
        # location = (x, y) # 위치 기반 검색은 서비스 지역 확대 시 구현
        result = admin.advanced_search(keyword)
        print(result)


if __name__ == '__main__':
    main()
