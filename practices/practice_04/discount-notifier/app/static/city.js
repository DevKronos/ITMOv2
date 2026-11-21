(() => {
  const form = document.querySelector('#city-form');
  if (!form) return;
  const input = form.elements.city;
  const button = form.querySelector('button');
  const feedback = document.querySelector('#city-feedback');
  let pending = false;
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (pending) return;
    const city = input.value.trim().replace(/\s+/g, ' ');
    if (!city || city.length > 100) {
      input.setAttribute('aria-invalid', 'true');
      feedback.textContent = 'Введите название города (до 100 символов).';
      feedback.className = 'city-feedback error';
      input.focus();
      return;
    }
    input.removeAttribute('aria-invalid');
    pending = true;
    button.disabled = true;
    button.textContent = 'Сохраняем…';
    feedback.className = 'city-feedback';
    feedback.textContent = 'Сохраняем город…';
    try {
      const response = await fetch('/api/city', {method: 'POST', body: new URLSearchParams({city})});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось сохранить город.');
      input.value = data.city;
      feedback.textContent = `Город сохранён: ${data.city}. Обновите страницу, чтобы пересчитать данные каталога и уведомлений.`;
      feedback.className = 'city-feedback success';
    } catch (error) {
      feedback.textContent = 'Не удалось сохранить город. Проверьте соединение и повторите попытку.';
      feedback.className = 'city-feedback error';
    } finally {
      pending = false;
      button.disabled = false;
      button.textContent = 'Сохранить город';
    }
  });
})();
