import datetime

from sanic import response

class Paginator:
    def __init__(self, query, page_size):
        self.query = query
        self.page_size = max(1, int(page_size)) 
        self._total_items = 0
        self._total_pages = 0
        self._items = []
        

    async def paginate(self, page:int=1):
        self._total_items = await self.query.count()
        self.page = max(1, int(page)) 
        self._total_pages = (self._total_items + self.page_size - 1) // self.page_size

        start = (self.page - 1) * self.page_size
        items = await self.query.offset(start).limit(self.page_size).all()

        self._items = items

    @property
    def items(self):
        return self._items
    
    @property
    def total_pages(self):
        return self._total_pages
    
    @property
    def total_items(self):
        return self._total_items

def http_response(code=None, msg=None, result=None, status=200, **kwargs):
    if not code and not msg:
        return response.HTTPResponse(status=status)
    output = {'code': code, 'msg': msg, 'results': result}
    if kwargs:
        output.update(kwargs)
    return response.json(output, status=status)

def get_timestamp():
    timestamp = int(datetime.datetime.utcnow().timestamp() * 1000)
    return timestamp

