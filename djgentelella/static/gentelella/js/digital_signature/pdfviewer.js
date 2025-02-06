const signature = document.getElementById('signature');
  var pdfDoc = null,
      pageNum = 1,
      pageRendering = false,
      pageNumPending = null,
      scale = 1.2,
      canvas = document.getElementById('pdfviewer'),
      ctx = canvas.getContext('2d'),
      signX = 0,
      signY = 198,
      signWidth = 133,
      signHeight = 133;


  function renderPage(num) {
    pageRendering = true;
    pdfDoc.getPage(num).then(function(page) {
      var viewport = page.getViewport({scale: scale});
      canvas.height = viewport.height;
      canvas.width = viewport.width;

      var renderContext = {
        canvasContext: ctx,
        viewport: viewport
      };
      var renderTask = page.render(renderContext);

      renderTask.promise.then(function() {
        pageRendering = false;
        if (pageNumPending !== null) {
          renderPage(pageNumPending);
          pageNumPending = null;
        }
      });
    });

    document.getElementById('page_num').textContent = num;
    document.getElementById('page_number').value= num;
  }



  function queueRenderPage(num) {
    if (pageRendering) {
      pageNumPending = num;
    } else {
      renderPage(num);
    }
  }


  function onPrevPage() {
    if (pageNum <= 1) {
      return;
    }
    pageNum--;
    queueRenderPage(pageNum);
  }
  document.getElementById('prev').addEventListener('click', onPrevPage);


  function onNextPage() {
    if (pageNum >= pdfDoc.numPages) {
      return;
    }
    pageNum++;
    queueRenderPage(pageNum);
  }
  document.getElementById('next').addEventListener('click', onNextPage);
  document.getElementById('page_number').addEventListener('change', function(e){
    renderPage(e.target.value);
  });
  document.getElementById('page_number').addEventListener('keyup', function(e){
    renderPage(e.target.value);
  });

  pdfjsLib.getDocument(pdf_document).promise.then(function(pdfDoc_) {
    pdfDoc = pdfDoc_;
    document.getElementById('page_count').textContent = pdfDoc.numPages;

    renderPage(pageNum);
  });


function send_request(url){
     fetch(url)
        .then(response => response.json())
        .then(data=>location.href=urls["return_verification"])
}

$("#send_analysis").on("click", function(e){
    send_request(urls["analysis"]);
})

$("#closed").on("click", function(e){
    send_request(urls["close"]);
})

interact('#signature')
    .draggable({
        inertia: true,
        modifiers: [
            interact.modifiers.restrictRect({
                restriction: document.getElementById('pdfviewer'),
                endOnly: false
            })
        ],
        autoScroll: true,
        listeners: {
            move: dragMoveListener,
            end(event) {
            }
        },
    }).resizable({
    // resize from all edges and corners
    edges: { left: true, right: true, bottom: true, top: true },

    listeners: {
      move (event) {
        var target = event.target
        var x = (parseFloat(target.getAttribute('data-x')) || 0)
        var y = (parseFloat(target.getAttribute('data-y')) || 0)

        // update the element's style
        target.style.width = event.rect.width + 'px'
        target.style.height = event.rect.height + 'px'

        // translate when resizing from top or left edges
        x += event.deltaRect.left
        y += event.deltaRect.top

        target.style.transform = 'translate(' + x + 'px,' + y + 'px)'

        target.setAttribute('data-x', x)
        target.setAttribute('data-y', y)
        target.textContent = Math.round(event.rect.width) + '\u00D7' + Math.round(event.rect.height)
        signWidth = event.rect.width;
        signHeight = event.rect.height;
        signX = x;
        signY = y;
      }
    },
    modifiers: [
      // keep the edges inside the parent
      interact.modifiers.restrictEdges({
        outer: 'parent'
      }),

      // minimum size
      interact.modifiers.restrictSize({
        min: { width: 100, height: 50 }
      })
    ],

    inertia: true
  })

function adjustPositionToFitWithinCanvas(target, x, y) {
    const canvas_rect = canvas.getBoundingClientRect();
    const target_rect = target.getBoundingClientRect();

    if (target_rect.right > canvas_rect.right) {
        x -= target_rect.right - canvas_rect.right;
    }
    if (target_rect.bottom > canvas_rect.bottom) {
        y -= target_rect.bottom - canvas_rect.bottom;
    }
    return {x, y};
}

function updatePosition(target, x, y) {
    target.style.transform = `translate(${x}px, ${y}px)`;

    const {x: x_adjusted, y: y_adjusted} = adjustPositionToFitWithinCanvas(target, x, y);

    target.style.transform = `translate(${x_adjusted}px, ${y_adjusted}px)`;
    target.setAttribute('data-x', x_adjusted);
    target.setAttribute('data-y', y_adjusted);

    const x_rounded = Math.round(x_adjusted);
    const y_rounded = Math.round(y_adjusted);

    signX = x_rounded;
    signY = y_rounded;
}

function dragMoveListener(event) {
    let target = event.target;
    let x = (parseFloat(target.getAttribute('data-x')) || 0) + event.dx;
    let y = (parseFloat(target.getAttribute('data-y')) || 0) + event.dy;
    updatePosition(target, x, y);

}

interact('#signature')
    .draggable({
        inertia: true,
        modifiers: [
            interact.modifiers.restrictRect({
                restriction: document.getElementById('pdfviewer'),
                endOnly: false
            })
        ],
        autoScroll: {
            container: document.getElementById('sub_canvas_container'),
            margin: 50,
            distance: 5,
            interval: 50
        },
        listeners: {
            move: dragMoveListener,
        },
    });

async function createTemporarySignature(content) {
    let temp_signature = signature.cloneNode(true);
    temp_signature.id = 'temp_signature';
    temp_signature.style.position = 'absolute';
    temp_signature.style.visibility = 'hidden';
    temp_signature.querySelector('#text').style.wordBreak = 'break-word';
    document.getElementById('sub_canvas_container').appendChild(temp_signature);
    await formatAndLoadContent(temp_signature, content);
    return temp_signature;
}

async function formatAndLoadContent(element, content) {
    const image_container = element.querySelector('#image');
    const text_container = element.querySelector('#text');
    image_container.innerHTML = '';
    text_container.innerHTML = '';
    try {
        //await loadSignatureImage(current_signature_image_url, image_container);
        //await updateTextContainer(text_container, formatted_text, content);
    } catch (error) {
        console.error(gettext("Error loading content: "), error);
    }
}

function updateSignatureDimensionInputsState(is_auto_resizable) {
    signature_width_input.disabled = is_auto_resizable;
    signature_height_input.disabled = is_auto_resizable;
    if (is_auto_resizable) {
        signature_width_input.value = signature.offsetWidth;
        signature_height_input.value = signature.offsetHeight;
    }
}

// Format and load content
function loadSignatureImage(signature_image, image_container) {
    return new Promise((resolve, reject) => {
        if (!signature_image) {
            resolve();
            return;
        }
        const img = new Image();
        img.src = signature_image;
        img.alt = 'signature-image';
        img.onload = () => {
            image_container.appendChild(img);
            resolve();
        };
        img.onerror = () => {
            reject(new Error(gettext("Error loading image")));
        };
    });
}

function applySettingToSignature() {
    const temp_signature = signature.cloneNode(true);
    temp_signature.style = '';
    temp_signature.classList.remove("right", "left", "top", "bottom", "full", "none");
    temp_signature.style.visibility = 'visible';

    temp_signature.style.width = 'auto';
    temp_signature.style.height = 'auto';
    temp_signature.style.overflow = 'visible';
    temp_signature.querySelector('#text').style.wordBreak = 'break-word';

    formatAndLoadContent(temp_signature)
        .then(() => {
            signature.className = temp_signature.className;
            signature.style.cssText = temp_signature.style.cssText;
            signature.innerHTML = temp_signature.innerHTML;
            //updateSignatureDimensionInputsState(is_auto_resizable);
            updatePosition(signature,198,0);
        })
        .catch(error => {
            console.error(gettext("Error when applying setting to signature: "), error);
        });
}

applySettingToSignature();

document.get_document_settings = function() {
    return {
        'pageNumber' : pageNum,
        'signWidth' : signWidth,
        'signHeight' : signHeight,
        'signX' : signX,
        'signY' : signY
    }
};


