{%comment%}Modal dialog for attach thread{%endcomment%}
<div class="modal fade" id="attachModal" role="dialog">
 <div class="modal-dialog modal-lg"><div class="modal-content">
  <div class="modal-header">
   <h3 class="modal-title">Attach thread</h3>
   <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
  </div>
  <div class="modal-body">
   <form class="d-flex gap-2" style="margin-bottom: 15px;">
    <input type="hidden" id="attachThreadAttachOnly" value="0">
    <div class="input-group">
     <input id="attachThreadSearchField" type="text" class="form-control" placeholder="Search subject or name">
     <button id="attachThreadSearchButton" onclick="return findLatestThreads()" class="btn btn-secondary">Search</button>
    </div>
   </form>
   <div class="mb-3">Pick one of the recent emails from pgsql-hackers, or search above for subject or name:</div>
   <div id="attachThreadListWrap" class="mb-3">
    <select id="attachThreadList" size="6" class="form-select" onchange="attachThreadChanged()">
    </select>
   </div>
   <div class="mb-2">Or enter an <i>exact</i> message id:</div>
   <input type="text" id="attachThreadMessageId" class="form-control" placeholder="Message id" onkeypress="attachThreadChanged()" onchange="attachThreadChanged()">
  </div>
  <div class="modal-footer">
   <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
   <button type="button" id="doAttachThreadButton" class="btn btn-primary disabled">Attach thread</button>
  </div>
 </div></div>
</div>
