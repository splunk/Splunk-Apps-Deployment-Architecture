require.config({
    paths: {
        buttercup_view: '../app/' + splunkjs.mvc.Components.getInstance("env").toJSON().app + '/js/views/ButtercupView'
    }
});

require([
    'jquery', 
    'underscore', 
    'splunkjs/mvc', 
    'buttercup_view', 
    'splunkjs/mvc/simplexml/ready!'], function ($, _, mvc, ButtercupView) {

        // Render the view on the page
        var buttercupView = new ButtercupView({
            el: $('#placeholder_for_view')
        });

        // Render the view
        buttercupView.render();
});