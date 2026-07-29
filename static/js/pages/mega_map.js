(function() {
    'use strict';

    function parseJsonScript(id) {
        var el = document.getElementById(id);
        if (!el) return null;
        try {
            return JSON.parse(el.textContent);
        } catch (e) {
            console.error('Failed to parse JSON script:', id, e);
            return null;
        }
    }

    function hexToRgb(hex) {
        var result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? {
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16)
        } : null;
    }

    function rgbToHex(r, g, b) {
        return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
    }

    function interpolateColor(color1, color2, ratio) {
        var c1 = hexToRgb(color1);
        var c2 = hexToRgb(color2);
        if (!c1 || !c2) return color1;
        var r = Math.round(c1.r + (c2.r - c1.r) * ratio);
        var g = Math.round(c1.g + (c2.g - c1.g) * ratio);
        var b = Math.round(c1.b + (c2.b - c1.b) * ratio);
        return rgbToHex(r, g, b);
    }

    function getSvetoforColor(percent) {
        if (percent === null || percent === undefined || isNaN(percent)) {
            return '#d1d5db';
        }
        var p = Math.max(0, Math.min(100, percent));
        if (p <= 50) {
            return interpolateColor('#ef4444', '#eab308', p / 50);
        } else {
            return interpolateColor('#eab308', '#22c55e', (p - 50) / 50);
        }
    }

    function calculateBounds(polygons) {
        var minLon = Infinity, maxLon = -Infinity;
        var minLat = Infinity, maxLat = -Infinity;

        polygons.forEach(function(obekt) {
            if (!obekt.area) return;
            obekt.area.forEach(function(feature) {
                if (!feature || !feature.geometry || !feature.geometry.coordinates) return;
                var coords = feature.geometry.coordinates;
                extractCoords(coords).forEach(function(c) {
                    minLon = Math.min(minLon, c[0]);
                    maxLon = Math.max(maxLon, c[0]);
                    minLat = Math.min(minLat, c[1]);
                    maxLat = Math.max(maxLat, c[1]);
                });
            });
        });

        return { minLon: minLon, maxLon: maxLon, minLat: minLat, maxLat: maxLat };
    }

    function extractCoords(coords) {
        var result = [];
        if (!coords || !coords.length) return result;

        if (Array.isArray(coords[0][0][0])) {
            coords.forEach(function(polygon) {
                if (polygon && polygon[0]) {
                    polygon[0].forEach(function(c) { result.push(c); });
                }
            });
        } else if (Array.isArray(coords[0][0])) {
            coords[0].forEach(function(c) { result.push(c); });
        }
        return result;
    }

    function coordsToPath(allParts, bounds) {
        var svgWidth = 1000;
        var svgHeight = 800;
        var padding = 50;
        var lonRange = bounds.maxLon - bounds.minLon;
        var latRange = bounds.maxLat - bounds.minLat;
        var scaleX = (svgWidth - 2 * padding) / lonRange;
        var scaleY = (svgHeight - 2 * padding) / latRange;

        var paths = [];
        allParts.forEach(function(ring) {
            var pathData = ring.map(function(coord, i) {
                var x = padding + (coord[0] - bounds.minLon) * scaleX;
                var y = svgHeight - (padding + (coord[1] - bounds.minLat) * scaleY);
                return (i === 0 ? 'M' : 'L') + x.toFixed(2) + ',' + y.toFixed(2);
            }).join(' ') + ' Z';
            paths.push(pathData);
        });
        return paths;
    }

    function getParts(obekt) {
        var allParts = [];
        if (!obekt.area) return allParts;

        obekt.area.forEach(function(feature) {
            if (!feature || !feature.geometry || !feature.geometry.coordinates) return;
            var rawCoords = feature.geometry.coordinates;

            if (Array.isArray(rawCoords[0][0][0])) {
                rawCoords.forEach(function(polygon) {
                    if (polygon && polygon[0]) {
                        allParts.push(polygon[0]);
                    }
                });
            } else if (Array.isArray(rawCoords[0][0])) {
                allParts.push(rawCoords[0]);
            }
        });
        return allParts;
    }

    function findMahallaName(obekt, index, mahallaNames) {
        var sectionId = obekt.section_id || obekt.id;

        if (sectionId && window.SECTION_ID_TO_MAHALLA_NAME && window.SECTION_ID_TO_MAHALLA_NAME[sectionId]) {
            return window.SECTION_ID_TO_MAHALLA_NAME[sectionId];
        }

        if (sectionId && mahallaNames) {
            var match = mahallaNames.find(function(m) {
                return m.id && m.id.toString().slice(-6) === sectionId;
            });
            if (match) return match.name;
        }

        if (mahallaNames && index < mahallaNames.length) {
            return mahallaNames[index].name;
        }

        if (sectionId) {
            var last6 = sectionId.toString().slice(-6);
            if (window.SECTION_ID_TO_MAHALLA_NAME && window.SECTION_ID_TO_MAHALLA_NAME[last6]) {
                return window.SECTION_ID_TO_MAHALLA_NAME[last6];
            }
        }

        return "Noma'lum";
    }

    function normalizeName(name) {
        return (name || '').replace(/\u041c\u0424\u0419/gi, '').replace(/['`\u02BB\u02BC]/g, '').trim().toLowerCase();
    }

    function findPercent(mahallaName, percentMap) {
        if (!percentMap) return null;
        var raw = null;
        if (percentMap[mahallaName] !== undefined) {
            raw = percentMap[mahallaName];
        } else {
            var normalized = normalizeName(mahallaName);
            var keys = Object.keys(percentMap);
            for (var i = 0; i < keys.length; i++) {
                if (normalizeName(keys[i]) === normalized) {
                    raw = percentMap[keys[i]];
                    break;
                }
            }
        }
        if (raw === null || raw === undefined) return null;
        var n = typeof raw === 'number' ? raw : parseFloat(String(raw).replace('%', ''));
        return isNaN(n) ? null : n;
    }

    function parsePercent(val) {
        if (val === null || val === undefined) return null;
        var n = typeof val === 'number' ? val : parseFloat(String(val).replace('%', ''));
        return isNaN(n) ? null : n;
    }

    function showTooltip(name, percent, event) {
        var tooltip = document.getElementById('mega-tooltip');
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.id = 'mega-tooltip';
            tooltip.className = 'mega-tooltip';
            document.body.appendChild(tooltip);
        }
        var num = parsePercent(percent);
        var percentText = num !== null ? num.toFixed(1) + '%' : 'Ma\'lumot yo\'q';
        tooltip.innerHTML = '<strong>' + name + '</strong><br>Bajarilish: ' + percentText;
        tooltip.style.display = 'block';
        tooltip.style.left = (event.pageX + 10) + 'px';
        tooltip.style.top = (event.pageY + 10) + 'px';
    }

    function hideTooltip() {
        var tooltip = document.getElementById('mega-tooltip');
        if (tooltip) tooltip.style.display = 'none';
    }

    function showErrorMessage(message) {
        var svg = document.getElementById('mega-svg-map');
        if (!svg) return;
        var text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', '50%');
        text.setAttribute('y', '50%');
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('fill', '#6b7280');
        text.setAttribute('font-size', '16');
        text.textContent = message;
        svg.appendChild(text);
    }

    function renderPolygons() {
        var polygons = window.MAHALLA_POLYGONS;
        var percentMap = parseJsonScript('mahalla-percent-data');
        var mahallaNames = parseJsonScript('mahalla-names-data');

        if (!polygons || !polygons.length) {
            showErrorMessage('Polygon ma\'lumotlari topilmadi');
            return;
        }

        var svg = document.getElementById('mega-svg-map');
        if (!svg) return;

        while (svg.firstChild) {
            svg.removeChild(svg.firstChild);
        }

        var bounds = calculateBounds(polygons);

        polygons.forEach(function(obekt, index) {
            var mahallaName = findMahallaName(obekt, index, mahallaNames);
            var percent = findPercent(mahallaName, percentMap);
            var color = getSvetoforColor(percent);

            var parts = getParts(obekt);
            if (parts.length === 0) return;

            var paths = coordsToPath(parts, bounds);

            paths.forEach(function(pathData) {
                var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                path.setAttribute('d', pathData);
                path.setAttribute('fill', color);
                path.setAttribute('stroke', '#374151');
                path.setAttribute('stroke-width', '1');
                path.setAttribute('opacity', '0.8');
                path.setAttribute('class', 'mega-polygon');
                path.setAttribute('data-mahalla', mahallaName);
                path.setAttribute('data-percent', percent || 0);

                path.addEventListener('mouseenter', function(e) {
                    this.setAttribute('opacity', '1');
                    this.setAttribute('stroke-width', '2');
                    showTooltip(mahallaName, percent, e);
                });

                path.addEventListener('mouseleave', function() {
                    this.setAttribute('opacity', '0.8');
                    this.setAttribute('stroke-width', '1');
                    hideTooltip();
                });

                path.addEventListener('mousemove', function(e) {
                    var tooltip = document.getElementById('mega-tooltip');
                    if (tooltip && tooltip.style.display === 'block') {
                        tooltip.style.left = (e.pageX + 10) + 'px';
                        tooltip.style.top = (e.pageY + 10) + 'px';
                    }
                });

                svg.appendChild(path);
            });
        });
    }

    window.MegaMapUtils = {
        getSvetoforColor: getSvetoforColor,
        interpolateColor: interpolateColor,
        normalizeName: normalizeName
    };

    document.addEventListener('DOMContentLoaded', renderPolygons);
})();
