// @vitest-environment jsdom
import {beforeEach, afterEach, describe, expect, it, vi} from 'vitest';
import {fireEvent, screen, waitFor} from '@testing-library/dom';
import userEvent from '@testing-library/user-event';
import {readFileSync} from 'node:fs';

const script = readFileSync('../practice_04/discount-notifier/app/static/city.js', 'utf8');
const template = readFileSync('../practice_04/discount-notifier/app/templates/index.html', 'utf8');
function mount(city = '') {
  const form = template.match(/<form id="city-form"[\s\S]*?<\/form>/)[0]
    .replace('{{ city }}', city)
    .replace("{{ 'Текущий город: ' ~ city if city else 'Город пока не выбран.' }}", city ? `Текущий город: ${city}` : 'Город пока не выбран.');
  document.body.innerHTML = form;
  window.eval(script);
}
const success = city => ({ok: true, json: async () => ({city})});
beforeEach(() => { vi.stubGlobal('fetch', vi.fn()); });
afterEach(() => { vi.unstubAllGlobals(); document.body.innerHTML = ''; });
describe('Выбор города', () => {
  it('показывает пустое состояние и проверяет обязательное поле и пробелы', async () => {
    mount(); const user = userEvent.setup();
    expect(screen.getByRole('status').textContent).toContain('Город пока не выбран');
    await user.type(screen.getByLabelText('Где искать предложения?'), '   ');
    await user.click(screen.getByRole('button', {name: 'Сохранить город'}));
    expect(screen.getByRole('status').textContent).toContain('Введите название города');
    expect(screen.getByLabelText('Где искать предложения?').getAttribute('aria-invalid')).toBe('true');
    expect(fetch).not.toHaveBeenCalled();
  });
  it('сохраняет введённый город и показывает ответ сервера', async () => {
    mount(); fetch.mockResolvedValue(success('Санкт-Петербург'));
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Где искать предложения?'), ' Санкт-Петербург ');
    await user.click(screen.getByRole('button', {name: 'Сохранить город'}));
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toBe('/api/city');
    expect(fetch.mock.calls[0][1].body.get('city')).toBe('Санкт-Петербург');
    expect(await screen.findByText(/Город сохранён: Санкт-Петербург/)).toBeTruthy();
    expect(screen.getByLabelText('Где искать предложения?').value).toBe('Санкт-Петербург');
  });
  it('отклоняет слишком длинное название и принимает Enter после исправления', async () => {
    mount();
    const input = screen.getByLabelText('Где искать предложения?');
    fireEvent.input(input, {target: {value: 'а'.repeat(101)}});
    fireEvent.submit(document.querySelector('form'));
    expect(screen.getByRole('status').textContent).toContain('до 100 символов');
    expect(fetch).not.toHaveBeenCalled();
    fetch.mockResolvedValue(success('Москва'));
    const user = userEvent.setup();
    await user.clear(input);
    await user.type(input, 'Москва{Enter}');
    expect(await screen.findByText(/Город сохранён: Москва/)).toBeTruthy();
  });
  it('во время задержки блокирует повторную отправку', async () => {
    mount('Москва'); let resolve;
    fetch.mockReturnValue(new Promise(r => { resolve = r; }));
    const form = document.querySelector('form'); fireEvent.submit(form); fireEvent.submit(form);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', {name: 'Сохраняем…'}).disabled).toBe(true);
    expect(screen.getByRole('status').textContent).toContain('Сохраняем');
    resolve(success('Москва'));
    await waitFor(() => expect(screen.getByRole('button', {name: 'Сохранить город'}).disabled).toBe(false));
  });
  it('позволяет повторить отправку после ошибки сервера', async () => {
    mount('Москва'); fetch.mockResolvedValueOnce({ok:false,json:async()=>({detail:'Ошибка'})}).mockResolvedValueOnce(success('Москва'));
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', {name: 'Сохранить город'}));
    expect(await screen.findByText(/Не удалось сохранить город/)).toBeTruthy();
    await user.click(screen.getByRole('button', {name: 'Сохранить город'}));
    expect(await screen.findByText(/Город сохранён: Москва/)).toBeTruthy();
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
