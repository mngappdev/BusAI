(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskNearbyPlaces = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  function groupByCategory(categories, places) {
    return categories.map((cat) => ({
      ...cat,
      places: places.filter((p) => p.category === cat.id),
    }));
  }

  // "Here" instead of "0m · 0 min walk" for places inside the same building
  // as the kiosk (e.g. Pasir Ris Mall, which the interchange is built into).
  function formatWalkLabel(distanceM, walkMinutes, lang) {
    if (distanceM < 20) {
      return lang === 'zh' ? '就在这里' : 'Here';
    }
    return lang === 'zh'
      ? `${distanceM}米 · 步行${walkMinutes}分钟`
      : `${distanceM}m · ${walkMinutes} min walk`;
  }

  function formatClosingLabel(closesAt, lang) {
    if (!closesAt) {
      return lang === 'zh' ? '24小时开放' : 'Open 24 hours';
    }
    if (lang === 'zh') {
      return `${closesAt} 打烊`;
    }
    const [hStr, mStr] = closesAt.split(':');
    const h24 = parseInt(hStr, 10);
    const period = h24 < 12 ? 'am' : 'pm';
    const h12 = h24 % 12 === 0 ? 12 : h24 % 12;
    return `Closes ${h12}:${mStr}${period}`;
  }

  return { groupByCategory, formatWalkLabel, formatClosingLabel };
});
