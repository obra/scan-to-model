'use strict';

const tour = window.MODEL_TOUR;
const select = document.querySelector('#contents');
const shot = document.querySelector('#shot');
let current = 0;
document.querySelector('#project').textContent = tour.title;
document.querySelector('#limits').textContent = tour.limits;
document.querySelector('#viewer-link').hidden = !tour.viewer;
for (const slide of tour.slides) select.add(new Option(slide.title, slide.id));

function show(index) {
  current = Math.max(0, Math.min(tour.slides.length - 1, index));
  const slide = tour.slides[current];
  shot.src = slide.image;
  shot.alt = slide.title;
  select.value = slide.id;
  document.querySelector('#title').textContent = slide.title;
  document.querySelector('#caption').textContent = slide.caption || '';
  document.querySelector('#count').textContent = `${current + 1} / ${tour.slides.length}`;
  document.querySelector('#previous').disabled = current === 0;
  document.querySelector('#next').disabled = current === tour.slides.length - 1;
  history.replaceState(null, '', '#' + slide.id);
}

select.addEventListener('change', () => show(tour.slides.findIndex(slide => slide.id === select.value)));
document.querySelector('#previous').addEventListener('click', () => show(current - 1));
document.querySelector('#next').addEventListener('click', () => show(current + 1));
window.addEventListener('keydown', event => {
  if (event.target.matches('select, input, textarea') || event.ctrlKey || event.metaKey || event.altKey) return;
  const target = { ArrowLeft: current - 1, ArrowRight: current + 1, Home: 0, End: tour.slides.length - 1 }[event.key];
  if (target !== undefined) { event.preventDefault(); show(target); }
});
show(Math.max(0, tour.slides.findIndex(slide => '#' + slide.id === location.hash)));
