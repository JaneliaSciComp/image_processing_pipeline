var config = config || {};

config.addCamParameter = function(text, doc, last) {
    const group = doc.createElement('div');
    group.classList.add('lightsheet-input');
    group.classList.add('input-group');
    group.classList.add('input-group-sm');

    const subgroup = doc.createElement('div');
    subgroup.classList.add('input-group-prepend');

    const span = doc.createElement('span');
    span.classList.add('lightsheet-input');
    span.classList.add('input-group-text');

    var text = doc.createTextNode(text);
    span.appendChild(text);
    subgroup.appendChild(span);

    const input = doc.createElement('input');
    input.setAttribute('type', 'number');
    input.setAttribute('aria-label', 'Small');
    input.setAttribute('aria-describedby', 'inputGroup-sizing-sm');

    group.appendChild(subgroup);
    group.appendChild(input)

    if (last) {
      group.classList.add('last-camera-parameter');
    } else {
      group.classList.add('middle-camera-parameter');
    }

    return group;
}

config.addCameraFields = function(){
  const doc = window.document;
  const camFields = doc.getElementById("camera-fields");
  camFields.innerHTML = '';
  const nrCameras = doc.getElementById('nr-cameras').value;
  if (!nrCameras || nrCameras == '') {
    alert('Please enter the number of cameras.');
    return;
  }
  const allParams = doc.createElement('div');
  for (let i = 0; i < nrCameras; i += 1) {
    const container = doc.createElement('div');
    const label = doc.createElement('label');
    var text = doc.createTextNode(`Camera ${i}`);
    label.appendChild(text);
    params1 = config.addCamParameter('Startsfront', doc, false);
    params2 = config.addCamParameter('Depth', doc, true);

    container.appendChild(label);
    container.appendChild(params1);
    container.appendChild(params2);
    allParams.appendChild(container);
  }
  camFields.appendChild(allParams);
}