/**
 * Resize function without multiple trigger
 *
 * Usage:
 * $(window).smartresize(function(){
 *     // code here
 * });
 */



(function ($, sr) {
    // debouncing function from John Hann
    // http://unscriptable.com/index.php/2009/03/20/debouncing-javascript-methods/
    var debounce = function (func, threshold, execAsap) {
        var timeout;

        return function debounced() {
            var obj = this,
                args = arguments;

            function delayed() {
                if (!execAsap)
                    func.apply(obj, args);
                timeout = null;
            }

            if (timeout)
                clearTimeout(timeout);
            else if (execAsap)
                func.apply(obj, args);

            timeout = setTimeout(delayed, threshold || 100);
        };
    };

    // smartresize
    jQuery.fn[sr] = function (fn) {
        return fn ? this.bind('resize', debounce(fn)) : this.trigger(sr);
    };
})(jQuery, 'smartresize');

/**
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */

var CURRENT_URL = window.location.href.split('#')[0].split('?')[0],
    $BODY = $('body'),
    $MENU_TOGGLE = $('#menu_toggle'),
    $SIDEBAR_MENU = $('#sidebar-menu'),
    $SIDEBAR_FOOTER = $('.sidebar-footer'),
    $LEFT_COL = $('.left_col'),
    $RIGHT_COL = $('.right_col'),
    $NAV_MENU = $('.nav_menu'),
    $FOOTER = $('footer');

// The one breakpoint the layout turns on, matching the media queries in
// gentelella/css/sidebar.css. matchMedia rather than $(window).width() so the
// two can never drift, and so crossing it fires an event we can react to.
var GT_NARROW = window.matchMedia('(max-width: 991.98px)');


// Sidebar
function init_sidebar() {
    // TODO: This is some kind of easy fix, maybe we can improve this
    var setContentHeight = function () {
        // reset height
        $RIGHT_COL.css('min-height', $(window).height());

        var bodyHeight = $BODY.outerHeight(),
            footerHeight = $BODY.hasClass('footer_fixed') ? -10 : $FOOTER.height(),
            leftColHeight = $LEFT_COL.eq(1).height() + $SIDEBAR_FOOTER.height(),
            contentHeight = bodyHeight < leftColHeight ? leftColHeight : bodyHeight;

        // normalize content
        contentHeight -= $NAV_MENU.height() + footerHeight;

        $RIGHT_COL.css('min-height', contentHeight);
    };

    $SIDEBAR_MENU.find('a').on('click', function (ev) {
        var $li = $(this).parent();
        // Its OWN submenu. `$('ul:first', $li)` searched descendants, so on a
        // level-1 entry it could pick up a level-3 list instead.
        var $ownMenu = $li.children('ul');

        // A parent entry is a disclosure, not a link: without this it both
        // opened the submenu and navigated away, so the levels underneath were
        // unreachable whenever the parent had a real url_name.
        if ($ownMenu.length) {
            ev.preventDefault();
        }

        if ($li.is('.active')) {
            $li.removeClass('active active-sm');
            $(this).attr('aria-expanded', 'false');
            $ownMenu.slideUp(function () {
                setContentHeight();
            });
        } else {
            // prevent closing menu if we are on child menu
            if (!$li.parent().is('.child_menu')) {
                $SIDEBAR_MENU.find('li').removeClass('active active-sm');
                if ($BODY.is(".nav-sm")) {
                    $li.find('.child_menu').show();
                }else{
                    $SIDEBAR_MENU.find('li ul').slideUp();
                }
            } else {
                if ($BODY.is(".nav-sm")) {
                    $SIDEBAR_MENU.find("li").removeClass("active active-sm");
                    $SIDEBAR_MENU.find("li ul").slideUp();
                    ev.preventDefault();
                }
            }
            $li.addClass('active');
            $(this).attr('aria-expanded', $ownMenu.length ? 'true' : null);

            $ownMenu.slideDown(function () {
                setContentHeight();
                positionRailFlyout($li);
            });
        }

        // A leaf on a narrow window is a navigation: do not leave the drawer
        // sitting over the page it just loaded.
        if (!$ownMenu.length && GT_NARROW.matches) {
            closeDrawer();
        }
    });

    // The collapsed rail's flyout is position:fixed, because #sidebar-menu now
    // scrolls and an absolutely positioned child of an overflow:auto box gets
    // clipped to the 70px rail. Fixed means we own top/left: put the flyout
    // beside the entry it belongs to, kept inside the window, instead of the
    // hardcoded `top: 80px` that dropped it on top of the rail.
    function positionRailFlyout($li) {
        var $menu = $li.children('ul.nav.child_menu');
        if (!$menu.length) {
            return;
        }
        if (!$BODY.hasClass('nav-sm') || GT_NARROW.matches) {
            $menu.css({top: '', left: ''});
            return;
        }
        var box = $li[0].getBoundingClientRect();
        var height = $menu.outerHeight();
        // Off the edge of the RAIL, not of the <li>: the list item is inset by
        // its own padding, so anchoring to it laid the flyout a few pixels
        // over the icons it is supposed to sit beside.
        var rail = $LEFT_COL.eq(0)[0].getBoundingClientRect();
        $menu.css({
            left: Math.max(box.right, rail.right) + 'px',
            top: Math.max(8, Math.min(box.top,
                window.innerHeight - height - 8)) + 'px'
        });
    }

    function repositionOpenFlyouts() {
        $SIDEBAR_MENU.find('> .menu_section > ul > li.active,'
            + ' > .menu_section > ul > li.active-sm').each(function () {
            positionRailFlyout($(this));
        });
    }

    $SIDEBAR_MENU.on('scroll', repositionOpenFlyouts);

    // -- the drawer, below the breakpoint ------------------------------------
    function openDrawer() {
        $BODY.addClass('sidebar-open');
        $MENU_TOGGLE.attr('aria-expanded', 'true');
        $SIDEBAR_MENU.find('a').first().trigger('focus');
    }

    function closeDrawer() {
        if (!$BODY.hasClass('sidebar-open')) {
            return;
        }
        $BODY.removeClass('sidebar-open');
        $MENU_TOGGLE.attr('aria-expanded', 'false');
        $MENU_TOGGLE.trigger('focus');
    }

    $('.sidebar-backdrop').on('click', closeDrawer);

    // A sidebar-footer icon is an action: log out, settings, or a panel like
    // the help palette. On a narrow window the drawer is the only way to reach
    // those icons, so leaving it open buries whatever was just opened under
    // the drawer and its backdrop -- the help panel opens at z-index 1035, the
    // drawer sits at 1040.
    $SIDEBAR_FOOTER.on('click', 'a', function () {
        if (GT_NARROW.matches) {
            closeDrawer();
        }
    });

    $(document).on('keydown', function (ev) {
        if (ev.key === 'Escape') {
            closeDrawer();
        }
    });

    // #menu_toggle is an <a> with no href, so it is not keyboard reachable on
    // its own; the template gives it role=button and tabindex, this makes the
    // keys work.
    $MENU_TOGGLE.on('keydown', function (ev) {
        if (ev.key === 'Enter' || ev.key === ' ') {
            ev.preventDefault();
            $(this).trigger('click');
        }
    });

    // Crossing the breakpoint: a rail inherited from a wide window would be a
    // 70px drawer, and a drawer left open would be an overlay nothing closes.
    GT_NARROW.addEventListener('change', function (ev) {
        $BODY.removeClass('sidebar-open');
        $MENU_TOGGLE.attr('aria-expanded', 'false');
        if (ev.matches && $BODY.hasClass('nav-sm')) {
            $SIDEBAR_MENU.find('li.active-sm')
                .addClass('active').removeClass('active-sm');
            $SIDEBAR_MENU.find('li.active > ul').show();
            $BODY.removeClass('nav-sm').addClass('nav-md');
        }
        repositionOpenFlyouts();
        setContentHeight();
    });

    // toggle small or large menu
    $MENU_TOGGLE.on('click', function () {
        // Below the breakpoint the sidebar is a drawer, not a rail. Stay in
        // nav-md -- none of the 70px rail rules should apply -- and never do
        // the active <-> active-sm swap, which would fold every open submenu
        // shut each time the drawer is opened.
        if (GT_NARROW.matches) {
            if ($BODY.hasClass('sidebar-open')) {
                closeDrawer();
            } else {
                openDrawer();
            }
            setContentHeight();
            return;
        }

        if ($BODY.hasClass('nav-md')) {
            $SIDEBAR_MENU.find('li.active ul').hide();
            $SIDEBAR_MENU.find('li.active').addClass('active-sm').removeClass('active');
        } else {
            $SIDEBAR_MENU.find('li.active-sm ul').show();
            $SIDEBAR_MENU.find('li.active-sm').addClass('active').removeClass('active-sm');
        }

        $BODY.toggleClass('nav-md nav-sm');

        repositionOpenFlyouts();
        setContentHeight();
    });

    // check active menu
    $SIDEBAR_MENU.find('a[href="' + CURRENT_URL + '"]').parent('li').addClass('current-page');

    $SIDEBAR_MENU.find('a').filter(function () {
        return this.href == CURRENT_URL;
    }).parent('li').addClass('current-page').parents('ul').slideDown(function () {
        setContentHeight();
    }).parent().addClass('active');

    // recompute content when resizing
    $(window).smartresize(function () {
        repositionOpenFlyouts();
        setContentHeight();
    });

    setContentHeight();

    // fixed sidebar
    if ($.fn.mCustomScrollbar) {
        $('.menu_fixed').mCustomScrollbar({
            autoHideScrollbar: true,
            theme: 'minimal',
            mouseWheel: { preventDefault: true }
        });
    }
};
// /Sidebar

var randNum = function () {
    return (Math.floor(Math.random() * (1 + 40 - 20))) + 20;
};

// Panel toolbox
$(document).ready(function () {
    $('.collapse-link').on('click', function () {
        var $BOX_PANEL = $(this).closest('.card'), //x_panel
            $ICON = $(this).find('i'),
            $BOX_CONTENT = $BOX_PANEL.find('.card-body'); //x_content

        // fix for some div with hardcoded fix class
        if ($BOX_PANEL.attr('style')) {
            $BOX_CONTENT.slideToggle(200, function () {
                $BOX_PANEL.removeAttr('style');
            });
        } else {
            $BOX_CONTENT.slideToggle(200);
            $BOX_PANEL.css('height', 'auto');
        }

        $ICON.toggleClass('fa-chevron-up fa-chevron-down');
    });

    $('.close-link').click(function () {
        var $BOX_PANEL = $(this).closest('.card');//x_panel

        $BOX_PANEL.remove();
    });
});
// /Panel toolbox

// Tooltip
$(document).ready(function () {
    $('[data-bs-toggle="tooltip"]').tooltip({
        container: 'body'
    });
});
// /Tooltip

// Switches are the .gt-switch class in gentelella/css/checks.css; there is
// nothing left to boot on ready.



// Table
$('table input[type=checkbox]').on('change', function () {
    if (!this.checked) { return; }
    checkState = '';
    $(this).parent().parent().parent().addClass('selected');
    countChecked();
});
$('table input[type=checkbox]').on('change', function () {
    if (this.checked) { return; }
    checkState = '';
    $(this).parent().parent().parent().removeClass('selected');
    countChecked();
});

var checkState = '';

$('.bulk_action input[type=checkbox]').on('change', function () {
    if (!this.checked) { return; }
    checkState = '';
    $(this).parent().parent().parent().addClass('selected');
    countChecked();
});
$('.bulk_action input[type=checkbox]').on('change', function () {
    if (this.checked) { return; }
    checkState = '';
    $(this).parent().parent().parent().removeClass('selected');
    countChecked();
});
$('.bulk_action input#check-all').on('change', function () {
    checkState = this.checked ? 'all' : 'none';
    countChecked();
});

function countChecked() {
    if (checkState === 'all') {
        $(".bulk_action input[name='table_records']").prop('checked', true);
    }
    if (checkState === 'none') {
        $(".bulk_action input[name='table_records']").prop('checked', false);
    }

    var checkCount = $(".bulk_action input[name='table_records']:checked").length;

    if (checkCount) {
        $('.column-title').hide();
        $('.bulk-actions').show();
        $('.action-cnt').html(checkCount + gettext(' Records Selected'));
    } else {
        $('.column-title').show();
        $('.bulk-actions').hide();
    }
}

// Accordion
$(document).ready(function () {
    $(".expand").on("click", function () {
        $(this).next().slideToggle(200);
        $expand = $(this).find(">:first-child");

        if ($expand.text() == "+") {
            $expand.text("-");
        } else {
            $expand.text("+");
        }
    });
});

// NProgress
if (typeof NProgress != 'undefined') {
        NProgress.start();
        NProgress.configure({ easing: 'ease', speed: 700 });
        //Increment
        $(document).ready(function(){
            NProgress.done();
        });
}
/**
// hover and retain popover when on popover content
var originalLeave = $.fn.popover.Constructor.prototype.leave;
$.fn.popover.Constructor.prototype.leave = function (obj) {
    var self = obj instanceof this.constructor ?
        obj : $(obj.currentTarget)[this.type](this.getDelegateOptions()).data('bs.' + this.type);
    var container, timeout;

    originalLeave.call(this, obj);

    if (obj.currentTarget) {
        container = $(obj.currentTarget).siblings('.popover');
        timeout = self.timeout;
        container.one('mouseenter', function () {
            // We entered the actual popover – call off the dogs
            clearTimeout(timeout);
            // Let's monitor popover content instead
            container.one('mouseleave', function () {
                $.fn.popover.Constructor.prototype.leave.call(self, self);
            });
        });
    }
};

$('body').popover({
    selector: '[data-bs-popover]',
    trigger: 'click hover',
    delay: {
        show: 50,
        hide: 400
    }
});
 **/
function gd(year, month, day) {
    return new Date(year, month - 1, day).getTime();
}

/* STARRR */

function init_starrr() {

    if (typeof (starrr) === 'undefined') {
        return;
    }
    $(".stars").starrr();

    $('.stars-existing').starrr({
        rating: 4
    });

    $('.stars').on('starrr:change', function (e, value) {
        $('.stars-count').html(value);
    });

    $('.stars-existing').on('starrr:change', function (e, value) {
        $('.stars-count-existing').html(value);
    });

};


function init_skycons() {

    if (typeof (Skycons) === 'undefined') {
        return;
    }

    var icons = new Skycons({
        "color": "#73879C"
    }),
        list = [
            "clear-day", "clear-night", "partly-cloudy-day",
            "partly-cloudy-night", "cloudy", "rain", "sleet", "snow", "wind",
            "fog"
        ],
        i;

    for (i = list.length; i--;)
        icons.set(list[i], list[i]);

    icons.play();

}

/* AUTOSIZE */

function init_autosize() {
    if (typeof $.fn.autosize !== 'undefined') {
        autosize($('.resizable_textarea'));
    }
};


function init_wysiwyg() {

    if (typeof ($.fn.wysiwyg) === 'undefined') {
        return;
    }

    function init_ToolbarBootstrapBindings() {
        var fonts = ['Serif', 'Sans', 'Arial', 'Arial Black', 'Courier',
            'Courier New', 'Comic Sans MS', 'Helvetica', 'Impact', 'Lucida Grande', 'Lucida Sans', 'Tahoma', 'Times',
            'Times New Roman', 'Verdana'
        ],
            fontTarget = $('[title=Font]').siblings('.dropdown-menu');
        $.each(fonts, function (idx, fontName) {
            fontTarget.append($('<li><a data-bs-edit="fontName ' + fontName + '" style="font-family:\'' + fontName + '\'">' + fontName + '</a></li>'));
        });
        $('a[title]').tooltip({
            container: 'body'
        });
        $('.dropdown-menu input').click(function () {
            return false;
        })
            .change(function () {
                $(this).parent('.dropdown-menu').siblings('.dropdown-toggle').dropdown('toggle');
            })
            .keydown('esc', function () {
                this.value = '';
                $(this).change();
            });

        $('[data-bs-role=magic-overlay]').each(function () {
            var overlay = $(this),
                target = $(overlay.data('target'));
            overlay.css('opacity', 0).css('position', 'absolute').offset(target.offset()).width(target.outerWidth()).height(target.outerHeight());
        });

        if ("onwebkitspeechchange" in document.createElement("input")) {
            var editorOffset = $('#editor').offset();

            $('.voiceBtn').css('position', 'absolute').offset({
                top: editorOffset.top,
                left: editorOffset.left + $('#editor').innerWidth() - 35
            });
        } else {
            $('.voiceBtn').hide();
        }
    }

    function showErrorAlert(reason, detail) {
        var msg = '';
        if (reason === 'unsupported-file-type') {
            msg = gettext("Unsupported format ") + detail;
        } else {
            console.log(gettext("error uploading file"), reason, detail);
        }
        $('<div class="alert"> <button type="button" class="close" data-bs-dismiss="alert">&times;</button>' +
            '<strong>File upload error</strong> ' + msg + ' </div>').prependTo('#alerts');
    }

    $('.editor-wrapper').each(function () {
        var id = $(this).attr('id'); //editor-one

        $(this).wysiwyg({
            toolbarSelector: '[data-bs-target="#' + id + '"]',
            fileUploadError: showErrorAlert
        });
    });


    window.prettyPrint;
    prettyPrint();

};


function init_validator() {

    if (typeof (validator) === 'undefined') {
        return;
    }

    // initialize the validator function
    validator.message.date = gettext('not a real date');

    // validate a field on "blur" event, a 'select' on 'change' event & a '.reuired' classed multifield on 'keyup':
    $('form')
        .on('blur', 'input[required], input.optional, select.required', validator.checkField)
        .on('change', 'select.required', validator.checkField)
        .on('keypress', 'input[required][pattern]', validator.keypress);

    $('.multi.required').on('keyup blur', 'input', function () {
        validator.checkField.apply($(this).siblings().last()[0]);
    });

    $('form').submit(function (e) {
        e.preventDefault();
        var submit = true;

        // evaluate the form using generic validaing
        if (!validator.checkAll($(this))) {
            submit = false;
        }

        if (submit)
            this.submit();

        return false;
    });

};

function init_input_text() {
    $('input[maxlength]').maxlength();
};


$(document).ready(function () {
    init_sidebar();
    init_input_text();
    $(".gencrud").listcrudrest();
    gt_find_initialize($('body'));
});

$(document).ready(function () {
    // For the Second level Dropdown menu, highlight the parent
    $(".dropdown-menu")
        .mouseenter(function () {
            $(this).parent('li').addClass('active');
        })
        .mouseleave(function () {
            $(this).parent('li').removeClass('active');
        });

    // Bootstrap 5 dropped submenus, so this project draws them itself with
    // `.dropdown-submenu:hover > .dropdown-menu`. Hover is not an interaction
    // a touch screen has, which left every nested top-menu entry unreachable
    // on a phone; open them on click as well.
    // An open dropdown is absolutely positioned, so it does not lengthen the
    // page: one opened near the bottom of a short window ran past the edge
    // with nothing able to scroll to its last entries. Cap it to the room
    // actually left below its own top and let it scroll inside that.
    function fitDropdownToViewport($menu) {
        if (!$menu || !$menu.length) {
            return;
        }
        $menu.css({'max-height': '', 'overflow-y': ''});
        // Only worth doing for a menu that is out of flow. An absolutely
        // positioned dropdown does not lengthen the page, so one opened near
        // the bottom of a short window has entries nothing can scroll to; a
        // static one is in flow and the page reaches it on its own. Capping a
        // static menu would clip it for no reason -- and above the breakpoint
        // a nested level flies out of this menu, which a scrolling parent
        // would clip.
        if (!GT_NARROW.matches
                || getComputedStyle($menu[0]).position === 'static') {
            return;
        }
        var top = $menu[0].getBoundingClientRect().top;
        $menu.css({
            'max-height': Math.max(60, window.innerHeight - top - 8) + 'px',
            'overflow-y': 'auto'
        });
    }

    function fitOpenDropdowns() {
        $('#items-top-navbar > li > .dropdown-menu.show')
            .each(function () { fitDropdownToViewport($(this)); });
    }

    $('#items-top-navbar').on('shown.bs.dropdown', fitOpenDropdowns);
    $(window).on('resize', fitOpenDropdowns);

    // Delegated from the menu, not from document: stopPropagation only stops
    // listeners further up, and Bootstrap's "a click closes every dropdown"
    // handler is bound to document itself. Catching the event here keeps it
    // from ever getting there.
    $('#items-top-navbar').on('click', '.dropdown-submenu > a', function (ev) {
        var $submenu = $(this).next('.dropdown-menu');
        if (!$submenu.length) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        // Siblings only: closing every open submenu would collapse the branch
        // the user is walking down.
        $(this).parent().siblings().find('> .dropdown-menu').removeClass('show');
        $submenu.toggleClass('show');
        // The branch just grew; the menu around it may no longer fit.
        fitOpenDropdowns();
    });

    // Leaving the parent dropdown resets its children, so the next opening
    // does not start half-unfolded.
    $(document).on('hide.bs.dropdown', function (ev) {
        $(ev.target).find('.dropdown-submenu > .dropdown-menu').removeClass('show');
    });
});


// The top navbar reverses its item order on wide viewports only.
//
// This used to read `screen.width` -- the physical display, not the window --
// so resizing the browser never re-evaluated it, and a narrow window on a big
// monitor got the wide layout. The `>=992 / <991` pair also left a window of
// exactly 991px matching neither branch. One matchMedia, one boundary, and it
// follows the window like the stylesheet does.
(function () {
    var wide = window.matchMedia('(min-width: 992px)');

    function applyTopNavbarOrder(matches) {
        $("#items-top-navbar").toggleClass("flex-row-reverse", matches);
    }

    wide.addEventListener('change', function (ev) {
        applyTopNavbarOrder(ev.matches);
    });
    $(function () {
        applyTopNavbarOrder(wide.matches);
    });
})()

/*
$('.dropdown-menu').on('click', function (e) {
  e.stopPropagation();

});
*/
