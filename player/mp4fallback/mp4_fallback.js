videojs.plugin('mp4fallback', function(options) {
  var player = this;
  player.on('loadedmetadata', function(e) {
    // only act if we're currently loaded on an MP4
    if (player.currentType().toLowerCase() === "video/mp4") {
      var sources = player.mediainfo.sources;
      // check to make sure we haven't already done this
      if (sources.length <= 1) {
        return;
      }

      // get the set that we want (it should only be one video)
      player.mediainfo.sources = [getDefaultMP4(player.mediainfo.sources, 360)];

      // remember if we were playing or not
      var playing = !player.paused();

      // and load it in
      player.catalog.load(player.mediainfo);
      if (playing) {
        player.one('loadedmetadata', function(e) {
          player.play();
        });
      }
    }
  });

  /*
   * getDefaultMP4
   * Takes an array of video sources and returns the one MP4 rendition that
   * is the largest resolution under the supplied target height but with the 
   * lowest bitrate.
   */ 
  function getDefaultMP4(sources, targetHeight) {
    // only one passed in?
    if (sources.length == 1)
      return sources[0];

    // remove all non-MP4 files and audio only MP4 files
    for (var i = 0; i < sources.length; ) {
      if (sources[i].container.toUpperCase() === 'MP4' &&
          sources[i].hasOwnProperty('src') &&
          sources[i].height >= 50)
        i++;
      else
        sources.splice(i, 1);
    }

    // sort by size with smallest first (since bitrate isn't provided)
    sources.sort(function(a, b) {
      return (a.size - b.size);
    });

    // get all that are smaller than the target
    var renditions = [];
    for (var i = 0; i < sources.length; i++) {
      if (sources[i].height <= targetHeight) {
        renditions.push(sources[i]);
      }
    }

    // fall back if we have nothing
    if (renditions.length == 0) {
      return sources[0];
    }

    // all that's left is getting the smallest rendition of the largest resolution
    var topRenditions = [];
    var topHeight = renditions[renditions.length - 1].height;
    for (var i = renditions.length - 1; i >= 0; i--) {
      if (renditions[i].height === topHeight) {
        topRenditions.push(renditions[i]);
      }
    }

    // and just retun the smalles of those
    return topRenditions[topRenditions.length - 1];
  }
});