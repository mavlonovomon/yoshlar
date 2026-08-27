(function () {
    "use strict";

    function parseJsonScript(id) {
        var el = document.getElementById(id);
        if (!el) return null;
        try { return JSON.parse(el.textContent); } catch (e) { return null; }
    }

    function getBaseStyle(youthCount, isSatellite) {
        return {
            color: "#ffffff",
            weight: isSatellite ? 2.5 : 2,
            opacity: 0.9,
            fill: false,
            fillOpacity: 0,
        };
    }

    function findMahallaName(sectionId) {
        // Hardcoded mapping first — handles name mismatches between Xarita and Django DB
        if (window.SECTION_ID_TO_MAHALLA_NAME && window.SECTION_ID_TO_MAHALLA_NAME[sectionId]) {
            return window.SECTION_ID_TO_MAHALLA_NAME[sectionId];
        }
        // Fallback: lookup by last 6 digits of id in MAHALLA_NAMES
        if (!window.MAHALLA_NAMES) return "Noma'lum";
        var match = window.MAHALLA_NAMES.find(function (m) {
            return m.id && m.id.slice(-6) === sectionId;
        });
        return match ? match.name : "Noma'lum";
    }

    function normalizeMahallaName(name) {
        return (name || '')
            .replace(/МФЙ/gi, '')
            .replace(/['ʻʼ`]/g, '')  // strip all apostrophe variants
            .trim()
            .toLowerCase();
    }

    function findMahallaStats(mahallaName, stats) {
        if (!stats) return null;
        // Try exact match first
        var exact = stats.find(function (s) {
            return s.name === mahallaName;
        });
        if (exact) return exact;

        // Fallback: normalized comparison (strip МФЙ, apostrophes, lowercase)
        var normalized = normalizeMahallaName(mahallaName);
        return stats.find(function (s) {
            return normalizeMahallaName(s.name) === normalized;
        });
    }

    function buildPopupContent(name, stats) {
        var html = '<div class="mahalla-popup">';
        html += '<div class="popup-title">' + name + '</div>';
        
        if (stats) {
            html += '<div class="stat-row"><span class="stat-label">Jami yoshlar</span><span class="stat-value text-primary">' + (stats.yosh_count || 0) + '</span></div>';
            html += '<div class="stat-row"><span class="stat-label">Ishsizlar</span><span class="stat-value text-danger">' + (stats.ishsiz_count || 0) + '</span></div>';
            html += '<div class="stat-row"><span class="stat-label">Migratsiya</span><span class="stat-value text-warning">' + (stats.migratsiya_count || 0) + '</span></div>';
            html += '<div class="stat-row"><span class="stat-label">Otaliqda</span><span class="stat-value text-info">' + (stats.otaliq_count || 0) + '</span></div>';
            html += '<div class="stat-row"><span class="stat-label">Suhbatlar</span><span class="stat-value text-success">' + (stats.suhbat_count || 0) + '</span></div>';
        } else {
            html += '<div class="text-muted small">Statistika topilmadi</div>';
        }
        
        html += '</div>';
        return html;
    }

    document.addEventListener("DOMContentLoaded", function () {
        var mapContainer = document.getElementById("mahalla-map");
        if (!mapContainer || typeof L === "undefined") return;

        var stats = parseJsonScript("mahalla-stats-data");

        // Initialize map centered on Hazorasp
        var map = L.map("mahalla-map", {
            zoomControl: true,
            scrollWheelZoom: true,
        }).setView([41.15, 61.24], 11);

        // Tile layers: standard + satellite
        var osmLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            maxZoom: 18,
        });

        var satelliteLayer = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
            attribution: "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics",
            maxZoom: 18,
        });

        // Custom pane for labels: above tiles, below polygons
        map.createPane("labelsPane");
        map.getPane("labelsPane").style.zIndex = 350;
        map.getPane("labelsPane").style.pointerEvents = "none";

        var labelsLayer = L.tileLayer("https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png", {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
            maxZoom: 18,
            pane: "labelsPane",
        });

        osmLayer.addTo(map);

        var satelliteActive = false;

        var polygonRecords = [];

        function applyPolygonStyles() {
            polygonRecords.forEach(function (record) {
                record.group.setStyle(getBaseStyle(record.youthCount, satelliteActive));
                record.group._baseStyle = getBaseStyle(record.youthCount, satelliteActive);
            });
        }

        L.control.layers({
            "Oddiy": osmLayer,
            "Sputnik": L.layerGroup([satelliteLayer, labelsLayer]),
        }, null, { position: "topright", collapsed: true }).addTo(map);

        map.on("baselayerchange", function (e) {
            satelliteActive = e.name === "Sputnik";
            applyPolygonStyles();
        });

        // Process polygons
        if (!window.MAHALLA_POLYGONS) return;

        var allPolygons = [];

        window.MAHALLA_POLYGONS.forEach(function (obekt) {
            var sectionId = obekt.section_id;
            var name = findMahallaName(sectionId);
            var mahallaStats = findMahallaStats(name, stats);
            var youthCount = mahallaStats ? (mahallaStats.yosh_count || 0) : 0;

            // Extract ALL polygon parts — handle Polygon and MultiPolygon
            var allParts = [];
            try {
                if (obekt.area && obekt.area[0] && obekt.area[0].geometry && obekt.area[0].geometry.coordinates) {
                    var rawCoords = obekt.area[0].geometry.coordinates;
                    // Check if MultiPolygon (array of polygons) or single Polygon
                    if (Array.isArray(rawCoords[0][0][0])) {
                        // MultiPolygon: rawCoords = [[polygon1_coords], [polygon2_coords], ...]
                        rawCoords.forEach(function (polygon) {
                            if (polygon[0]) {
                                allParts.push(polygon[0].map(function (c) { return [c[1], c[0]]; }));
                            }
                        });
                    } else if (Array.isArray(rawCoords[0][0])) {
                        // Single Polygon: rawCoords = [[exterior_ring, ...holes]]
                        allParts.push(rawCoords[0].map(function (c) { return [c[1], c[0]]; }));
                    }
                }
            } catch (e) {
                return; // skip invalid polygon
            }

            if (allParts.length === 0) return;

            // Create a feature group for all polygon parts
            var group = L.featureGroup();
            var baseStyle = getBaseStyle(youthCount, satelliteActive);

            allParts.forEach(function(partCoords) {
                var polygon = L.polygon(partCoords, baseStyle);
                group.addLayer(polygon);
            });

            group._baseStyle = baseStyle;
            group.addTo(map);
            polygonRecords.push({ group: group, youthCount: youthCount });

            // Hover effect on all parts
            group.eachLayer(function(layer) {
                layer.on("mouseover", function() {
                    group.eachLayer(function(l) { l.setStyle({ weight: 4 }); });
                });
                layer.on("mouseout", function() {
                    group.eachLayer(function(l) { l.setStyle(group._baseStyle); });
                });
                layer.on("click", function() {
                    var popupHtml = buildPopupContent(name, mahallaStats);
                    group.bindPopup(popupHtml, { maxWidth: 280, className: "mahalla-popup" }).openPopup();
                });
            });
        });

        // Fit map to show all polygons
        if (polygonRecords.length > 0) {
            var bounds = L.latLngBounds([]);
            polygonRecords.forEach(function (record) {
                bounds.extend(record.group.getBounds());
            });
            map.fitBounds(bounds, { padding: [20, 20] });
        }
    });
})();
