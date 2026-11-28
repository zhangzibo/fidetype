(function(){
var RM=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
var EV=[
  ['header','The spec version, the vocabulary (characters, keys, words, phonemes or commands), the source, the clock and meta keys such as device.modality.'],
  ['frame','A probability distribution over the vocabulary at one time. Many frames follow, one per time step.'],
  ['frame','Another time step. A frame can be dense or sparse.'],
  ['signal_quality','The quality of the input signal. It is separate from the decoder’s confidence.'],
  ['hypothesis','A ranked list of texts (n-best), with revisions and evidence.'],
  ['segment_end','The end of one segment: an utterance, a word or a trial.'],
  ['trust_decision','The output of the trust layer: COMMIT, OFFER, ASK or ABSTAIN. It names the frozen configuration, so an auditor can reproduce it.'],
  ['end','The end of the stream.']
];
var tl=document.getElementById('tl'),evd=document.getElementById('evd'),btns=[];
EV.forEach(function(e,i){var b=document.createElement('button');b.type='button';b.className='ev'+(e[0]==='trust_decision'?' trust':'');b.textContent=e[0];b.setAttribute('aria-pressed','false');
  b.addEventListener('click',function(){pick(i);stop()});tl.appendChild(b);btns.push(b)});
function pick(i){btns.forEach(function(b,k){b.setAttribute('aria-pressed',String(k===i));b.classList.toggle('lit',k<i)});evd.innerHTML='<b>'+EV[i][0]+'</b> · '+EV[i][1]}
var i=0,t=null;function stop(){clearInterval(t);t=null}
pick(0);
if(!RM&&'IntersectionObserver' in window){new IntersectionObserver(function(es){if(es[0].isIntersecting&&!t&&i===0){t=setInterval(function(){i++;if(i>=EV.length){stop();return}pick(i)},1500)}},{threshold:.5}).observe(tl)}
})();
