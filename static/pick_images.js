

async function copyImage(form) {
  // 1. Create a url-encoded form structure
  const formData = new URLSearchParams();
  for(const elem of form.querySelectorAll('input')) {
    formData.append(elem.name, elem.value);
  }

  try {
    const response = await fetch('/copy_image', {
      method: 'POST',
      headers: {
        // Required for manual key-value form strings
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: formData
    });

    let tr = form.parentNode;
    while(tr.tagName!='TR') {
      tr = tr.parentNode;
    }

    // reload image
    const firstImg = tr.querySelectorAll('img')[0];
    firstImg.src = (new URL(firstImg.src, location)).pathname + '?' + Math.random();

    if (response.ok) {
       console.log('Data transmitted successfully!');
    }
  } catch (error) {
    console.error(error);
  }
}
