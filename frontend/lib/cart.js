const CART_KEY = "ousus_cart";

function read() {
  if (typeof window === "undefined") return { items: [], custom: [] };
  try {
    const raw = localStorage.getItem(CART_KEY);
    if (!raw) return { items: [], custom: [] };
    const parsed = JSON.parse(raw);
    return { items: parsed.items || [], custom: parsed.custom || [] };
  } catch {
    return { items: [], custom: [] };
  }
}

function write(cart) {
  if (typeof window === "undefined") return;
  localStorage.setItem(CART_KEY, JSON.stringify(cart));
}

export function getCart() {
  return read();
}

export function addItem(item) {
  const cart = read();
  cart.items.push(item);
  write(cart);
  return cart;
}

export function addCustom(entry) {
  const cart = read();
  cart.custom.push(entry);
  write(cart);
  return cart;
}

export function removeLine(kind, index) {
  const cart = read();
  if (kind === "item") cart.items.splice(index, 1);
  else cart.custom.splice(index, 1);
  write(cart);
  return cart;
}

export function setQty(index, qty) {
  const cart = read();
  if (cart.items[index]) cart.items[index].qty = qty;
  write(cart);
  return cart;
}

export function clearCart() {
  write({ items: [], custom: [] });
}
