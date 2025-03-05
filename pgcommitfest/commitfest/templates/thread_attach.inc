{%comment%}Modal dialog for attach thread{%endcomment%}
<div class="modal fade" id="attachModal" role="dialog">
 <div class="modal-dialog modal-lg"><div class="modal-content">
  <div class="modal-header">
   <button type="button" class="close" data-dismiss="modal" aria-hidden="true">&times;</button>
   <h3>Attach thread</h3>
  </div>
  <div class="modal-body">
   <form class="form-inline" style="margin-bottom: 5px;">
    <input type="hidden" id="attachThreadAttachOnly" value="0">
    <div class="input-append">
     <input id="attachThreadSearchField" type="text" class="span2 search-query">
     <button id="attachThreadSearchButton" onclick="return findLatestThreads()" class="btn btn-default disabled">Search</button>
    </div>
   </form>
   <div>Pick one of the recent emails from pgsql-hackers, or search above for subject or name:</div>
   <div id="attachThreadListWrap">
    <select id="attachThreadList" size="6" style="width:100%;" onchange="attachThreadChanged()">
    </select>
   </div>
   <div>Or enter an <i>exact</i> message id:</div>
   <input type="text" id="attachThreadMessageId" placeholder="Message id" onkeypress="attachThreadChanged()" onchange="attachThreadChanged()">
  </div>
  <div class="modal-footer">
   <a href="#" class="btn btn-default" data-dismiss="modal">Close</a>
   <a href="#" id="doAttachThreadButton" class="btn btn-default btn-primary disabled">Attach thread</a>
  </div>
 </div></div>
</div>
