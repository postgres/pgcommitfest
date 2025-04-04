{%load commitfest%}
<div class="workflow">
 <table class="table table-bordered">
 <thead>
  <tr>
  <th>Assign To</th>
  <th>Annotate</th>
  <th>Resolve</th>
  <th>Move To</th>
  </tr>
 </thead>
 <tbody>
  <tr>
  <!-- Change -->
  <td>
     <a class="btn btn-default" href="status/review/">Needs review</a>
     <a class="btn btn-default" href="status/author/">Waiting on Author</a>
     <a class="btn btn-default" href="status/committer/">Ready for Committer</a>
  </td>
  <!-- Annotate -->
  <td>
   <a class="btn btn-default" href="comment/">Comment</a>
   <a class="btn btn-default" href="review/">Review</a>
  </td>
  <!-- Resolve -->
  <td>
     <a class="btn btn-default" href="close/reject/" onclick="return verify_reject()">Rejected</a>
     <a class="btn btn-default" href="close/withdrawn/" onclick="return verify_withdrawn()">Withdrawn</a>
     <a class="btn btn-default" href="close/feedback/" onclick="return verify_returned()">Returned with feedback</a>
     <a class="btn btn-default" href="close/next/?cfid={{cf.id}}" onclick="return verify_next()">Move to next CF</a>
     <a class="btn btn-default" href="close/committed/" onclick="return flagCommitted({%if patch.committer%}'{{patch.committer}}'{%elif is_committer%}'{{user.username}}'{%else%}null{%endif%})">Committed</a>
  </td>
  <!-- Move -->
  <td>
   /transition Actions Will Go Here (Deprecate Next)
  </td>
  </tr>
  <tr>
  <!-- Change -->
  <td>
   {%for author in authors %}
    <div>{{author.first_name}} {{author.last_name}}</div>
   {%endfor%}
  </td>
  <!-- Annotate -->
  <td>
   {%for reviewer in reviewers %}
    <div>{{reviewer.first_name}} {{reviewer.last_name}}</div>
   {%endfor%}
   <div><a href="reviewer/{{is_reviewer|yesno:"remove,become"}}/" class="btn btn-default">{{is_reviewer|yesno:"Remove from reviewers,Become reviewer"}}</a></div>
  </td>
  <!-- Resolve -->
  <td>
   {%if patch.committer%}<div>{{patch.committer.fullname}}</div>{%endif%}
   {%if is_committer%}<div><a href="committer/{{is_this_committer|yesno:"remove,become"}}/" class="btn btn-default">{{is_this_committer|yesno:"Unclaim as committer,Claim as committer"}}</a></div>{%endif%}
  </td>
  <!-- Move -->
  <td>
   <div>
    <span class="label label-{{poc.commitfest.status|patchstatuslabel}}">{{poc.commitfest.statusstring}}</span>
    <span class="label label-{{poc.status|patchstatuslabel}}">{{poc.statusstring}}</span>
    <span><a href="edit/">Version</a>: </span> <span class="label label-default">{%if patch.targetversion%}{{patch.targetversion}}{%else%}N/A{%endif%}</span>
    {%if user.is_authenticated%}
     <span class="pull-right">Updates: <a href="{{is_subscribed|yesno:"unsubscribe,subscribe"}}/" class="btn btn-default">{{is_subscribed|yesno:"Unsubscribe,Subscribe"}}</a></span>
    {%endif%}
   </div>
   <div>
    <span><a href="edit/">Topic</a>: </span></span> <span>{{ patch.topic }}</span>
   </div>
   <div>
    <span>Last Modified:</span> <span>{{patch.modified}} ({% cfwhen patch.modified %})</span>
   </div>
  </td>
  </tr>
 </tbody>
 </table>
</div>
