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