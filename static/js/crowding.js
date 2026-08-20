(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KioskCrowding = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  const LOAD_TO_LEVEL = {
    '有座': 'green',
    '较挤': 'amber',
    '拥挤': 'red',
  };

  const LEVEL_LABEL_KEYS = {
    green: 'quiet',
    amber: 'moderate',
    red: 'crowded',
    gray: 'noLiveData',
  };

  function levelForLoad(load) {
    return LOAD_TO_LEVEL[load] || 'gray';
  }

  function labelKeyForLevel(level) {
    return LEVEL_LABEL_KEYS[level] || LEVEL_LABEL_KEYS.gray;
  }

  return { LOAD_TO_LEVEL, LEVEL_LABEL_KEYS, levelForLoad, labelKeyForLevel };
});
