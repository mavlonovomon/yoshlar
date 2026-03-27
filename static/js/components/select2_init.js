(function (window) {
    "use strict";

    function initSelect2(context) {
        if (typeof window.jQuery === "undefined" || typeof window.jQuery.fn.select2 === "undefined") {
            return;
        }
        var root = context || document;
        window.jQuery(root)
            .find(".select2")
            .each(function () {
                var $el = window.jQuery(this);
                if ($el.hasClass("select2-hidden-accessible")) {
                    return;
                }
                $el.select2({
                    theme: "classic",
                    width: "100%"
                });
            });
    }

    window.initSelect2 = initSelect2;

    document.addEventListener("DOMContentLoaded", function () {
        initSelect2(document);
    });
})(window);
