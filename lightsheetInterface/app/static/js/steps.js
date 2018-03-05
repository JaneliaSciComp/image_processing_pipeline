var ls = ls || {};
ls.processForm = function() {
  var forms = document.getElementsByClassName('step-form');
  for (var i = 0; i < forms.length; i++) {
    forms[i].submit();
  }
}

// $(document).ready(function(){
//   console.log('hit the script');
//   var pipelineOrder = ['clusterPT', 'clusterMF', 'localAP', 'clusterTF', 'localEC', 'clusterCS', 'clusterFR'];
//   for (var i=0; i < pipelineOrder.length; i++) {
//     var pipelineStep = pipelineOrder[i];
//     var element = 'collapse' + pipelineStep;
//     $('#' + element).on(
//     "shown.bs.collapse", function(){
//       console.log('in function');
//       if(!document.getElementById('check-' + pipelineStep).checked) {
//         console.log('toggle check');
//         document.getElementById('check-' + pipelineStep).checked = true;
//       }
//     });
//   }
// });