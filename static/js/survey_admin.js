document.addEventListener('DOMContentLoaded', function() {
    function toggleChoicesField(row) {
        var typeSelect = row.querySelector('.field-question_type select');
        var choicesField = row.querySelector('.field-choices_text');
        
        // Sometimes Django renders inputs with slightly different class or id structure
        if (!typeSelect) {
            var selects = row.querySelectorAll('select[name$="-question_type"]');
            if (selects.length > 0) typeSelect = selects[0];
        }
        if (!choicesField) {
            var textareas = row.querySelectorAll('textarea[name$="-choices_text"]');
            if (textareas.length > 0) {
                // Find parent container (.form-row)
                choicesField = textareas[0].closest('.form-row') || textareas[0].closest('div');
            }
        }

        if (!typeSelect || !choicesField) return;

        var selectedType = typeSelect.value;
        var needsChoices = ['radio', 'checkbox', 'select', 'buttons'].includes(selectedType);
        
        if (needsChoices) {
            choicesField.style.display = '';
        } else {
            choicesField.style.display = 'none';
        }
    }

    function initRows() {
        var allRows = document.querySelectorAll('.inline-related');
        allRows.forEach(function(row) {
            toggleChoicesField(row);
            var select = row.querySelector('select[name$="-question_type"]');
            if(select) {
                select.addEventListener('change', function() {
                    toggleChoicesField(row);
                });
            }
        });
    }

    initRows();

    if (typeof django !== 'undefined' && django.jQuery) {
        django.jQuery(document).on('formset:added', function(event, $row, formsetName) {
            var row = $row[0];
            toggleChoicesField(row);
            var select = row.querySelector('select[name$="-question_type"]');
            if(select) {
                select.addEventListener('change', function() {
                    toggleChoicesField(row);
                });
            }
        });
    }
});
