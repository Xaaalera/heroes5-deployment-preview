#pragma once
#include <windows.h>
#include <algorithm>
#include <array>
#include <cwchar>
#include <string>
#include "deployment_comparison.hpp"
#include "../game-api/include/h5/native_ui.hpp"

namespace h5_preview {
// A view of the already formatted, frozen comparison. No battle calculation or
// SDK transport belongs to this native rendering backend.
struct NativeComparisonContent {
    int columns=0,rows=0;
    uint32_t battle=0,entries=0,neutralEntries=0;
    const int (*positions)[5]=nullptr;
    const bool (*visible)[2]=nullptr;
    const wchar_t (*details)[1536]=nullptr;
    const wchar_t* status=nullptr;
    const PlacementFieldSnapshot* field=nullptr;
    int (*rowLabel)(int)=nullptr;
    const wchar_t* title=nullptr;
    const wchar_t* forecastTitle=nullptr;
    const wchar_t* actualTitle=nullptr;
    const wchar_t* closeCaption=nullptr;
    const wchar_t* ownPrefix=L"";
};

class NativeComparisonWindow {
    struct Widget { uint32_t window=0,text=0,state=0;int entry=-1; };
    inline static HWND owner=nullptr;
    inline static uint32_t root=0,overlay=0,panel=0,details=0,status=0,closeButton=0;
    inline static uint32_t launcherParent=0,launcherCaption=0;
    inline static uint32_t closeCaption=0;
    inline static bool launcherCaptionReady=false;
    inline static uint32_t cellTemplate=0,rowTemplate=0,rosterTemplate=0;
    inline static std::array<uint32_t,2> grids{};
    inline static std::array<std::array<uint32_t,32>,2> rowWindows{};
    inline static std::array<std::array<Widget,1024>,2> cells{};
    inline static std::array<std::array<Widget,21>,2> tokens{};
    inline static std::array<Widget,21> roster{};
    inline static int builtColumns=0,builtRows=0,cellSize=0;
    inline static float builtViewportWidth=0,secondGridLeft=430;
    inline static uint32_t builtBattle=0;
    inline static bool attempted=false,open=false;
    inline static bool removalUnconfirmed=false;
    inline static uint32_t pendingParent=0,pendingChild=0,pendingBeforeCount=0;
    inline static std::array<uint32_t,128> pendingBefore{};
    using MutationState=h5::ui::NativeWindowMutationState;
    static bool Completed(const h5::ui::NativeWindowMutation& result,uint32_t operation,uint32_t target) {
        if (result.state==MutationState::Completed) { return true; }
        SetPropW(owner,L"H5Comparison.NativeFailureOperation.v1",reinterpret_cast<HANDLE>(uintptr_t{operation}));
        SetPropW(owner,L"H5Comparison.NativeFailureNode.v1",reinterpret_cast<HANDLE>(uintptr_t{target}));
        SetPropW(owner,L"H5Comparison.NativeFailureState.v1",reinterpret_cast<HANDLE>(uintptr_t{static_cast<uint32_t>(result.state)+1}));
        return false;
    }

    static bool Read(uint32_t address,void* output,size_t bytes) {
        __try { std::memcpy(output,reinterpret_cast<const void*>(address),bytes);return true; }
        __except(EXCEPTION_EXECUTE_HANDLER) { return false; }
    }
    static uint32_t Child(uint32_t parent,const char* name) {
        std::array<uint32_t,128> children{};uint32_t count=0;
        if (!h5::ui::ReadNativeWindowChildren(Read,parent,children,count)) { return 0; }
        for (uint32_t index=0;index<count;++index) {
            h5::ui::NativeWindowSnapshot child{};
            if (h5::ui::ReadNativeWindow(Read,children[index],child) && std::strcmp(child.name,name)==0) { return children[index]; }
        }
        return 0;
    }
    static bool Text(uint32_t window,const std::wstring& text) {
        return Completed(h5::ui::SetNativeWindowText(owner,window,text.c_str(),static_cast<uint32_t>(text.size())),1,window);
    }
    static bool Place(uint32_t window,float x,float y,float width,float height) {
        return Completed(h5::ui::SetNativeWindowPlacement(owner,window,x,y,width,height,15),2,window);
    }
    static bool Visible(uint32_t window,bool value) {
        return Completed(h5::ui::SetNativeWindowVisible(owner,window,value),3,window);
    }
    static uint32_t Clone(uint32_t parent,uint32_t model) {
        std::array<uint32_t,128> before{};uint32_t count=0;
        if (pendingParent || !h5::ui::ReadNativeWindowChildren(Read,parent,before,count)) { return 0; }
        const auto result=h5::ui::CreateNativeWindowChild(owner,parent,model);
        if (result.state==MutationState::Unconfirmed) {
            pendingParent=parent;pendingChild=result.child;pendingBefore=before;pendingBeforeCount=count;
        }
        return Completed(result,4,parent) ? result.child : 0;
    }
    static bool RetireChild(uint32_t parent,uint32_t& child) {
        if (!child) { return true; }
        std::array<uint32_t,128> children{};uint32_t count=0;
        if (!h5::ui::ReadNativeWindowChildren(Read,parent,children,count)) { return false; }
        if (std::find(children.begin(),children.begin()+count,child)==children.begin()+count) {
            child=0;removalUnconfirmed=false;return true;
        }
        // A queued/uncertain removal is observed, never submitted twice.
        if (removalUnconfirmed || !Visible(child,false)) { return false; }
        if (!Completed(h5::ui::RemoveNativeWindowChild(owner,parent,child),9,child)) {
            removalUnconfirmed=true;return false;
        }
        child=0;return true;
    }
    static bool State(Widget& widget,uint32_t value) {
        if (widget.state==value) { return true; }
        const auto result=h5::ui::ConsumeNativeButtonState(owner,widget.window,widget.state,value);
        if (!Completed(result,5,widget.window)) { return false; }
        widget.state=value;return true;
    }
    static bool Bind(HWND game,uint32_t combatRoot) {
        if ((pendingParent || removalUnconfirmed) && !Reset()) { return false; }
        if (root==combatRoot && overlay && panel && details && status && closeButton && cellTemplate && rowTemplate && rosterTemplate && grids[0] && grids[1]) { return true; }
        if (!Reset()) { return false; }
        owner=game;root=combatRoot;
        RemovePropW(owner,L"H5Comparison.NativeFailureOperation.v1");
        RemovePropW(owner,L"H5Comparison.NativeFailureNode.v1");
        RemovePropW(owner,L"H5Comparison.NativeFailureState.v1");
        overlay=Child(root,"DeploymentOverlay");panel=Child(overlay,"DeploymentPanel");
        if (!overlay || !panel) { return false; }
        details=Child(panel,"DeploymentDetails");status=Child(panel,"DeploymentStatus");
        if (!details) {
            const auto scroll=Child(panel,"DeploymentDetailsScroll");
            details=Child(scroll,"DeploymentDetails");
            if (!details) { details=Child(Child(scroll,"DeploymentDetailsBorder"),"DeploymentDetails"); }
            if (!details && !h5::ui::ReadNativeScrollTextWindow(Read,scroll,details)) { return false; }
        }
        closeButton=Child(panel,"DeploymentClose");cellTemplate=Child(panel,"DeploymentCellTemplate");
        rowTemplate=Child(panel,"DeploymentRowTemplate");rosterTemplate=Child(panel,"DeploymentRosterTemplate");
        grids={Child(panel,"DeploymentForecastGrid"),Child(panel,"DeploymentActualGrid")};
        return details && status && closeButton && cellTemplate && rowTemplate && rosterTemplate && grids[0] && grids[1];
    }
    static bool Build(const NativeComparisonContent& content) {
        if (builtBattle==content.battle && builtColumns==content.columns && builtRows==content.rows) { return true; }
        if (attempted) { return false; }
        attempted=true;
        if (!content.battle || content.columns<1 || content.columns>29 || content.rows<1 || content.rows>31 ||
            !content.entries || content.entries>roster.size() || !content.positions || !content.visible || !content.details ||
            !content.status || !content.field || !content.rowLabel) { return false; }
        h5::ui::NativeWindowSnapshot arena{};
        if (!h5::ui::ReadNativeWindow(Read,root,arena) || arena.width<1024 || arena.height<768) { return false; }
        const float panelWidth=(std::min)(1100.0f,arena.width-32);
        const float rosterWidth=(std::max)(200.0f,panelWidth*255/1100);
        const float rosterLeft=panelWidth-35-rosterWidth;
        const float fieldWidth=(rosterLeft-35-20)/2;
        secondGridLeft=35+fieldWidth+10;
        cellSize=(std::min)(static_cast<int>(fieldWidth-30)/content.columns,300/content.rows);
        if (cellSize<8) { return false; }
        const auto scroll=Child(panel,"DeploymentDetailsScroll");
        const auto border=Child(scroll,"DeploymentDetailsBorder");
        const float detailsWidth=rosterLeft-55;
        if (!Place(panel,0,0,panelWidth,700) ||
            !Place(Child(panel,"DeploymentTitle"),35,20,panelWidth-70,32) ||
            !Place(status,35,56,panelWidth-70,36) ||
            !Place(Child(panel,"DeploymentForecastTitle"),35,94,fieldWidth,28) ||
            !Place(Child(panel,"DeploymentActualTitle"),secondGridLeft,94,fieldWidth,28) ||
            !Place(closeButton,(panelWidth-136)/2,628,136,49) ||
            !Place(scroll,35,445,detailsWidth,180) || !Place(border,0,0,detailsWidth-20,180)) { return false; }
        for (uint32_t phase=0;phase<2;++phase) {
            if (!Place(grids[phase],phase ? secondGridLeft : 35.0f,126,
                static_cast<float>(content.columns*cellSize+30),static_cast<float>(content.rows*cellSize))) { return false; }
            for (int row=0;row<content.rows;++row) {
                auto& rowWindow=rowWindows[phase][row];rowWindow=Clone(grids[phase],rowTemplate);
                if (!rowWindow || !Place(rowWindow,0,static_cast<float>(row*cellSize),
                    static_cast<float>(content.columns*cellSize+30),static_cast<float>(cellSize))) { return false; }
                const auto label=Child(rowWindow,"DeploymentRowNumber");
                wchar_t number[80]{};swprintf_s(number,L"<center><font face=System size=16><color_white>%d",content.rowLabel(row));
                if (!label || !Place(label,static_cast<float>(content.columns*cellSize),(cellSize-20)/2.0f,30,20) || !Text(label,number)) { return false; }
                for (int column=0;column<content.columns;++column) {
                    auto& cell=cells[phase][row*32+column];cell.window=Clone(rowWindow,cellTemplate);
                    if (!cell.window) { return false; }
                    cell.text=Child(cell.window,"DeploymentCellText");
                    if (!cell.text || !Place(cell.window,static_cast<float>(column*cellSize+1),1,static_cast<float>(cellSize-2),static_cast<float>(cellSize-2)) ||
                        !Place(cell.text,0,static_cast<float>((std::max)(0,(cellSize-22)/2)),static_cast<float>(cellSize-2),20) || !Visible(cell.window,true)) { return false; }
                }
                if (!Visible(rowWindow,true)) { return false; }
            }
            for (uint32_t index=0;index<content.entries;++index) {
                if (!content.visible[index][phase]) { continue; }
                auto& token=tokens[phase][index];token.window=Clone(grids[phase],cellTemplate);
                if (!token.window) { return false; }
                token.text=Child(token.window,"DeploymentCellText");token.entry=static_cast<int>(index);
                const int* position=content.positions[index];const float size=static_cast<float>(position[4]*cellSize);
                if (!token.text || !Place(token.window,static_cast<float>(position[phase*2]*cellSize+1),static_cast<float>(position[phase*2+1]*cellSize+1),size-2,size-2) ||
                    !Place(token.text,0,(size-22)/2,size-2,20) || !Visible(token.window,true)) { return false; }
            }
        }
        for (uint32_t index=0;index<content.entries;++index) {
            auto& item=roster[index];item.window=Clone(panel,rosterTemplate);
            if (!item.window || !Place(item.window,rosterLeft,126+static_cast<float>(index*24),rosterWidth,24)) { return false; }
            item.text=Child(item.window,"DeploymentRosterText");
            if (!item.text || !Place(item.text,3,0,rosterWidth-6,24) || !Visible(item.window,true)) { return false; }
            item.entry=static_cast<int>(index);
        }
        if (content.title && !Text(Child(panel,"DeploymentTitle"),std::wstring(L"<center><font face=Button size=16><color_header>")+content.title)) { return false; }
        if (content.forecastTitle && !Text(Child(panel,"DeploymentForecastTitle"),std::wstring(L"<center><font face=Button size=16><color_white>")+content.forecastTitle)) { return false; }
        if (content.actualTitle && !Text(Child(panel,"DeploymentActualTitle"),std::wstring(L"<center><font face=Button size=16><color_white>")+content.actualTitle)) { return false; }
        if (content.closeCaption) {
            closeCaption=Clone(closeButton,Child(panel,"DeploymentTitle"));
            if (!closeCaption || !Text(closeCaption,std::wstring(L"<center><font face=Button size=16><color_header>")+content.closeCaption) ||
                !Place(closeCaption,6,14,124,24) || !Visible(closeCaption,true)) { return false; }
        }
        if (scroll) {
            h5::ui::NativeWindowSnapshot viewport{};
            if (!h5::ui::ReadNativeWindow(Read,Child(scroll,"DeploymentDetailsBorder"),viewport)) { return false; }
            // Text height is computed by native reflow. Restore only width,
            // including after HMR; static resource widgets outlive the payload.
            const auto resized=h5::ui::SetNativeWindowPlacement(owner,details,0,0,viewport.width,0,4);
            if (!Completed(resized,2,details)) { return false; }
        }
        builtColumns=content.columns;builtRows=content.rows;builtBattle=content.battle;builtViewportWidth=arena.width;return true;
    }
    static bool Paint(const NativeComparisonContent& content,int selected) {
        if (selected<0 || static_cast<uint32_t>(selected)>=content.entries) { return false; }
        for (uint32_t phase=0;phase<2;++phase) {
            for (int row=0;row<content.rows;++row) {
                for (int column=0;column<content.columns;++column) {
                    auto& cell=cells[phase][row*32+column];cell.entry=-1;
                    uint32_t color=content.field->version==1 &&
                        (content.field->blockedRows[content.rows-row]&(1u<<(column+2))) ? 1u : 0u;
                    for (uint32_t index=0;index<content.entries;++index) {
                        const int* position=content.positions[index];const int left=position[phase*2],top=position[phase*2+1],size=position[4];
                        if (content.visible[index][phase] && column>=left && column<left+size && row>=top && row<top+size) {
                            cell.entry=static_cast<int>(index);break;
                        }
                    }
                    wchar_t caption[80]{};
                    if (color==1) { wcscpy_s(caption,L"<center><font face=System size=16><color_white>X"); }
                    if (!State(cell,color*2) || !Text(cell.text,caption)) { return false; }
                }
            }
            for (uint32_t index=0;index<content.entries;++index) {
                auto& token=tokens[phase][index];if (!token.window) { continue; }
                uint32_t color=index>=content.neutralEntries ? 4u : phase ? 3u : 2u;
                if (static_cast<int>(index)==selected) { color=5; }
                wchar_t caption[96]{};swprintf_s(caption,L"<center><font face=System size=16><color_white><outline>%s%u",
                    index>=content.neutralEntries ? content.ownPrefix : L"",index>=content.neutralEntries ? index-content.neutralEntries+1 : index+1);
                if (!State(token,color*2) || !Text(token.text,caption)) { return false; }
            }
        }
        for (uint32_t index=0;index<content.entries;++index) {
            const std::wstring description=content.details[index];const auto end=description.find(L'\u00b7');
            const auto number=index>=content.neutralEntries ? index-content.neutralEntries+1 : index+1;
            const auto color=static_cast<int>(index)==selected ? L"<color_header>" : L"<color_white>";
            if (!Text(roster[index].text,std::wstring(L"<left><font face=System size=16>")+color+
                (index>=content.neutralEntries ? content.ownPrefix : L"")+std::to_wstring(number)+L". "+description.substr(0,end))) { return false; }
        }
        if (!Text(status,L"<left><font face=System size=16><color_white>"+std::wstring(content.status)) ||
            !Text(details,L"<left><font face=System size=16><color_white><forcewrap>"+std::wstring(content.details[selected]))) { return false; }
        const auto scroll=Child(panel,"DeploymentDetailsScroll");
        if (scroll && !Completed(h5::ui::UpdateNativeScrollText(owner,scroll,details),6,details)) { return false; }
        SetPropW(owner,L"H5Comparison.NativeSelection.v1",reinterpret_cast<HANDLE>(uintptr_t{static_cast<uint32_t>(selected)+1}));
        SetPropW(owner,L"H5DeploymentComparison.Selection.v1",reinterpret_cast<HANDLE>(uintptr_t{static_cast<uint32_t>(selected)+1}));return true;
    }
public:
    static bool UpdateLauncher(HWND game,uint32_t combatRoot,uint32_t launcher,const wchar_t* caption) {
        if (!Bind(game,combatRoot)) { return false; }
        h5::ui::NativeWindowSnapshot arena{},timeline{};
        const auto atb=Child(combatRoot,"ATBBar");
        if (!atb || !h5::ui::ReadNativeWindow(Read,combatRoot,arena) ||
            !h5::ui::ReadNativeWindow(Read,atb,timeline)) { return false; }
        const float left=(std::max)(0.0f,(std::min)(timeline.left,arena.width-136));
        const float top=(std::max)(0.0f,timeline.top-49-2);
        h5::ui::NativeWindowSnapshot button{};
        if (!h5::ui::ReadNativeWindow(Read,launcher,button)) { return false; }
        if ((button.left!=left || button.top!=top || button.width!=136 || button.height!=49) &&
            !Place(launcher,left,top-arena.height+49,136,49)) { return false; }
        if (launcherCaptionReady) { return true; }
        if (!launcherCaption) {
            launcherParent=launcher;
            launcherCaption=Clone(launcher,Child(panel,"DeploymentTitle"));
            if (!launcherCaption) { return false; }
        }
        launcherCaptionReady=Text(launcherCaption,std::wstring(L"<center><font size=14><color_header>")+caption) &&
            Place(launcherCaption,6,14,124,24) && Visible(launcherCaption,true);
        return launcherCaptionReady;
    }
    static bool IsOpen() { return open; }
    static bool Available(HWND game,uint32_t combatRoot) {
        return game && Child(combatRoot,"DeploymentOverlay")!=0;
    }
    static bool Show(HWND game,uint32_t combatRoot,const NativeComparisonContent& content,int selected) {
        h5::ui::NativeWindowSnapshot arena{};
        if (root==combatRoot && builtViewportWidth && h5::ui::ReadNativeWindow(Read,combatRoot,arena) && arena.width!=builtViewportWidth && !Reset()) { return false; }
        if (!Bind(game,combatRoot) || !Build(content) || !Paint(content,selected) || !Visible(overlay,true)) { return false; }
        if (!Completed(h5::ui::SetNativeWindowModalInput(owner,overlay,true),7,overlay)) { Visible(overlay,false);return false; }
        open=true;
        SetPropW(owner,L"H5Comparison.NativePanelOpen.v1",reinterpret_cast<HANDLE>(uintptr_t{1}));
        SetPropW(owner,L"H5Comparison.NativePanel.v1",reinterpret_cast<HANDLE>(uintptr_t{overlay}));
        SetPropW(owner,L"H5Comparison.NativePanelBattle.v1",reinterpret_cast<HANDLE>(uintptr_t{content.battle+1}));return true;
    }
    static void Tick(const NativeComparisonContent& content,int& selected) {
        if (!open || !owner || builtBattle!=content.battle) { return; }
        bool visible=false;
        if (!h5::ui::ReadNativeWindowVisible(Read,overlay,visible)) { return; }
        if (!visible) {
            Completed(h5::ui::SetNativeWindowModalInput(owner,overlay,false),8,overlay);
            open=false;RemovePropW(owner,L"H5Comparison.NativePanelOpen.v1");RemovePropW(owner,L"H5DeploymentComparison.OpenBattle.v1");return;
        }
        h5::ui::NativeWindowSnapshot viewport{};
        if (h5::ui::ReadNativeWindow(Read,root,viewport) && viewport.width!=builtViewportWidth) {
            Show(owner,root,content,selected);return;
        }
        if (h5::ui::ConsumeNativeButtonState(owner,closeButton,1,0).state==MutationState::Completed) {
            if (Visible(overlay,false)) {
                Completed(h5::ui::SetNativeWindowModalInput(owner,overlay,false),8,overlay);
                open=false;RemovePropW(owner,L"H5Comparison.NativePanelOpen.v1");RemovePropW(owner,L"H5DeploymentComparison.OpenBattle.v1");
            }
            return;
        }
        int next=selected;
        for (uint32_t index=0;index<content.entries;++index) {
            if (h5::ui::ConsumeNativeButtonState(owner,roster[index].window,1,0).state==MutationState::Completed) { next=static_cast<int>(index); }
        }
        POINT pointer{};RECT client{};h5::ui::NativeWindowSnapshot arena{},frame{};
        if (GetCursorPos(&pointer) && ScreenToClient(owner,&pointer) && GetClientRect(owner,&client) && client.right>0 && client.bottom>0 &&
            h5::ui::ReadNativeWindow(Read,root,arena) && h5::ui::ReadNativeWindow(Read,panel,frame)) {
            const float x=pointer.x*arena.width/client.right-frame.left,y=pointer.y*arena.height/client.bottom-frame.top;
            for (uint32_t phase=0;phase<2;++phase) {
                const float gridLeft=phase ? secondGridLeft : 35;
                const int column=static_cast<int>((x-gridLeft)/cellSize),row=static_cast<int>((y-126)/cellSize);
                if (x<gridLeft || y<126 || column<0 || column>=builtColumns || row<0 || row>=builtRows) { continue; }
                auto& cell=cells[phase][row*32+column];
                auto& target=cell.entry>=0 ? tokens[phase][cell.entry] : cell;
                if (h5::ui::ConsumeNativeButtonState(owner,target.window,target.state+1,target.state).state==MutationState::Completed && target.entry>=0) { next=target.entry; }
            }
        }
        if (next!=selected && Paint(content,next)) { selected=next; }
    }
    static bool Reset() {
        bool present=false;
        if (owner && root && !h5::ui::ReadNativeCombatRootPresence(Read,root,present)) { return false; }
        if (owner && root && present) {
            if (overlay) { Completed(h5::ui::SetNativeWindowModalInput(owner,overlay,false),8,overlay); }
            if (overlay) { Visible(overlay,false); }
            open=false;
            RemovePropW(owner,L"H5Comparison.NativePanelOpen.v1");
            if (pendingParent) {
                std::array<uint32_t,128> children{};uint32_t count=0;
                if (!h5::ui::ReadNativeWindowChildren(Read,pendingParent,children,count)) { return false; }
                uint32_t added=0;
                for (uint32_t index=0;index<count;++index) {
                    if (std::find(pendingBefore.begin(),pendingBefore.begin()+pendingBeforeCount,children[index])!=pendingBefore.begin()+pendingBeforeCount) { continue; }
                    if (added && added!=children[index]) { return false; }
                    added=children[index];
                }
                if (added && pendingChild && added!=pendingChild) { return false; }
                pendingChild=added;
                if (!RetireChild(pendingParent,pendingChild)) { return false; }
                pendingParent=0;pendingBeforeCount=0;pendingBefore={};removalUnconfirmed=false;
            }
            for (uint32_t phase=0;phase<2;++phase) {
                for (auto& token:tokens[phase]) {
                    if (!RetireChild(grids[phase],token.window)) { return false; }
                }
                for (auto& row:rowWindows[phase]) {
                    if (!RetireChild(grids[phase],row)) { return false; }
                }
            }
            for (auto& item:roster) { if (!RetireChild(panel,item.window)) { return false; } }
            if (!RetireChild(closeButton,closeCaption)) { return false; }
            if (!RetireChild(launcherParent,launcherCaption)) { return false; }
        }
        if (owner) { RemovePropW(owner,L"H5Comparison.NativePanel.v1");RemovePropW(owner,L"H5Comparison.NativePanelBattle.v1");RemovePropW(owner,L"H5Comparison.NativePanelOpen.v1");RemovePropW(owner,L"H5Comparison.NativeSelection.v1"); }
        owner=nullptr;root=overlay=panel=details=status=closeButton=cellTemplate=rowTemplate=rosterTemplate=0;
        launcherParent=launcherCaption=0;
        closeCaption=0;
        launcherCaptionReady=false;
        grids={};rowWindows={};cells={};tokens={};roster={};builtColumns=builtRows=cellSize=0;builtBattle=0;attempted=open=false;
        builtViewportWidth=0;secondGridLeft=430;
        removalUnconfirmed=false;pendingParent=pendingChild=pendingBeforeCount=0;pendingBefore={};return true;
    }
};
}
