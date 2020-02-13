
def get_title(item):
    if item.only_icon:
        return ''
    return item.title

def get_link(item, env={}):
    return  item.url_name