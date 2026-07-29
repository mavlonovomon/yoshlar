(function() {
    'use strict';

    // Parse JSON from template script tags
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

    // Convert hex color to RGB object
    function hexToRgb(hex) {
        var result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? {
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16)
        } : null;
    }

    // Convert RGB to hex color
    function rgbToHex(r, g, b) {
        return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
    }

    // Interpolate between two colors
    function interpolateColor(color1, color2, ratio) {
        var c1 = hexToRgb(color1);
        var c2 = hexToRgb(color2);
        
        if (!c1 || !c2) return color1;
        
        var r = Math.round(c1.r + (c2.r - c1.r) * ratio);
        var g = Math.round(c1.g + (c2.g - c1.g) * ratio);
        var b = Math.round(c1.b + (c2.b - c1.b) * ratio);
        
        return rgbToHex(r, g, b);
    }

    // Calculate svetofor color based on percentage
    function getSvetoforColor(percent) {
        if (percent === null || percent === undefined || isNaN(percent)) {
            return '#d1d5db'; // gray for no data
        }
        
        var p = Math.max(0, Math.min(100, percent)); // clamp 0-100
        
        if (p <= 50) {
            // Red to Yellow gradient (0-50%)
            var ratio = p / 50;
            return interpolateColor('#ef4444', '#eab308', ratio);
        } else {
            // Yellow to Green gradient (50-100%)
            var ratio = (p - 50) / 50;
            return interpolateColor('#eab308', '#22c55e', ratio);
        }
    }

    // Calculate bounding box for all polygons
    function calculateBounds(polygons) {
        var minLon = Infinity, maxLon = -Infinity;
        var minLat = Infinity, maxLat = -Infinity;
        
        polygons.forEach(function(obekt) {
            if (!obekt.area || !obekt.area[0] || !obekt.area[0].geometry) {
                return;
            }
            
            var coords = obekt.area[0].geometry.coordinates;
            var allCoords = [];
            
            // Handle MultiPolygon and Polygon
            if (Array.isArray(coords[0][0][0])) {
                // MultiPolygon: coords = [[polygon1], [polygon2], ...]
                coords.forEach(function(polygon) {
                    if (polygon[0]) {
                        allCoords = allCoords.concat(polygon[0]);
                    }
                });
            } else if (Array.isArray(coords[0][0])) {
                // Polygon: coords = [[ring]]
                allCoords = coords[0];
            }
            
            allCoords.forEach(function(coord) {
                var lon = coord[0];
                var lat = coord[1];
                minLon = Math.min(minLon, lon);
                maxLon = Math.max(maxLon, lon);
                minLat = Math.min(minLat, lat);
                maxLat = Math.max(maxLat, lat);
            });
        });
        
        return { 
            minLon: minLon, 
            maxLon: maxLon, 
            minLat: minLat, 
            maxLat: maxLat 
        };
    }

    // Convert GeoJSON coordinates to SVG path string
    function geoJsonToSvgPath(coordinates, bounds) {
        var svgWidth = 1000;
        var svgHeight = 800;
        var padding = 50;
        
        var scaleX = (svgWidth - 2 * padding) / (bounds.maxLon - bounds.minLon);
        var scaleY = (svgHeight - 2 * padding) / (bounds.maxLat - bounds.minLat);
        
        var pathData = coordinates.map(function(coord, index) {
            var lon = coord[0];
            var lat = coord[1];
            
            var x = padding + (lon - bounds.minLon) * scaleX;
            var y = svgHeight - (padding + (lat - bounds.minLat) * scaleY); // flip Y
            
            return (index === 0 ? 'M' : 'L') + x.toFixed(2) + ',' + y.toFixed(2);
        }).join(' ') + ' Z'; // close path
        
        return pathData;
    }

    // Find mahalla name by section_id (reuse logic from dashboard_map.js)
    function findMahallaName(sectionId, mahallaNames) {
        // Try hardcoded mapping first
        if (window.SECTION_ID_TO_MAHALLA_NAME && window.SECTION_ID_TO_MAHALLA_NAME[sectionId]) {
            return window.SECTION_ID_TO_MAHALLA_NAME[sectionId];
        }
        
        // Fallback: match by last 6 digits
        if (!mahallaNames) return "Noma'lum";
        
        var match = mahallaNames.find(function(m) {
            return m.id && m.id.toString().slice(-6) === sectionId;
        });
        
        return match ? match.name : "Noma'lum";
    }

    // Show tooltip on hover
    function showTooltip(name, percent, event) {
        var tooltip = document.getElementById('mega-tooltip');
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.id = 'mega-tooltip';
            tooltip.className = 'mega-tooltip';
            document.body.appendChild(tooltip);
        }
        
        var percentText = (percent !== null && percent !== undefined) 
            ? percent.toFixed(1) + '%' 
            : 'Ma\'lumot yo\'q';
        
        tooltip.innerHTML = '<strong>' + name + '</strong><br>Bajarilish: ' + percentText;
        tooltip.style.display = 'block';
        tooltip.style.left = (event.pageX + 10) + 'px';
        tooltip.style.top = (event.pageY + 10) + 'px';
    }

    // Hide tooltip
    function hideTooltip() {
        var tooltip = document.getElementById('mega-tooltip');
        if (tooltip) {
            tooltip.style.display = 'none';
        }
    }

    // Show error message in SVG
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

    // Main render function
    function renderPolygons() {
        var polygons = window.MAHALLA_POLYGONS;
        var percentMap = parseJsonScript('mahalla-percent-data');
        var mahallaNames = parseJsonScript('mahalla-names-data');
        
        if (!polygons || !polygons.length) {
            console.warn('No polygon data found');
            showErrorMessage('Polygon ma\'lumotlari topilmadi');
            return;
        }
        
        if (!percentMap) {
            console.warn('No percent data found');
            percentMap = {};
        }
        
        var svg = document.getElementById('mega-svg-map');
        if (!svg) {
            console.error('SVG element not found');
            return;
        }
        
        // Clear existing polygons
        while (svg.firstChild) {
            svg.removeChild(svg.firstChild);
        }
        
        var bounds = calculateBounds(polygons);
        
        polygons.forEach(function(obekt) {
            var sectionId = obekt.section_id;
            var mahallaName = findMahallaName(sectionId, mahallaNames);
            var percent = percentMap[mahallaName];
            var color = getSvetoforColor(percent);
            
            if (!obekt.area || !obekt.area[0] || !obekt.area[0].geometry) {
                return; // skip invalid
            }
            
            var rawCoords = obekt.area[0].geometry.coordinates;
            var allParts = [];
            
            // Handle MultiPolygon and Polygon
            if (Array.isArray(rawCoords[0][0][0])) {
                // MultiPolygon
                rawCoords.forEach(function(polygon) {
                    if (polygon[0]) {
                        allParts.push(polygon[0]);
                    }
                });
            } else if (Array.isArray(rawCoords[0][0])) {
                // Polygon
                allParts.push(rawCoords[0]);
            }
            
            // Create SVG path for each part
            allParts.forEach(function(coords) {
                var pathData = geoJsonToSvgPath(coords, bounds);
                
                var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                path.setAttribute('d', pathData);
                path.setAttribute('fill', color);
                path.setAttribute('stroke', '#374151');
                path.setAttribute('stroke-width', '1');
                path.setAttribute('opacity', '0.8');
                path.setAttribute('class', 'mega-polygon');
                path.setAttribute('data-mahalla', mahallaName);
                path.setAttribute('data-percent', percent || 0);
                
                // Hover effects
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

    // Export for testing
    window.MegaMapUtils = {
        parseJsonScript: parseJsonScript,
        getSvetoforColor: getSvetoforColor,
        interpolateColor: interpolateColor
    };

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', renderPolygons);
})();
