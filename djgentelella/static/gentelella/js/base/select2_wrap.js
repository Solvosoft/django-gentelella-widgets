function decore_select2 (data) {
    // We only really care if there is an element to pull classes from
    if (!data.element) {
      return data.text;
    }
    var $element = $(data.element);
    var $wrapper = $('<span></span>');
    $wrapper.addClass($element[0].className);
    $wrapper.text(data.text);
    return $wrapper;
}

function decore_img_select2 (data) {
  if(!data.url && data.text){
      return $('<span>'+data.text+'</span>');
  }
  if (!data.url) {
    return "";
  }
  let img_width = "2em";   let img_height="2em;";
  if(data.img_width != undefined){img_width=data.img_width;}
  if(data.img_height != undefined){ img_height=data.img_height; }
  var $state = $('<span><img style="width: '+img_width+'; height: '+img_height+';" src="' + data.url+ '" class="img-flag" /> ' +  data.text + '</span>');
  return $state;
};
